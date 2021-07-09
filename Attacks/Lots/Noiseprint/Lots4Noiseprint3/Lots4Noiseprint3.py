import logging
import os
from math import ceil

import numpy as np
from tqdm import tqdm

from Attacks.Lots.Noiseprint.Lots4NoiseprintBase import Lots4NoiseprintBase, normalize_gradient
from Attacks.utilities.visualization import visuallize_array_values
from Detectors.Noiseprint.Noiseprint.noiseprint import NoiseprintEngine, normalize_noiseprint
from Ulitities.Image.Patch import Patch
from Ulitities.Image.Picture import Picture


class LotsNoiseprint3(Lots4NoiseprintBase):

    def __init__(self, objective_image: Picture, objective_mask: Picture, target_representation_image: Picture = None,
                 target_representation_mask: Picture = None, qf: int = None,
                 patch_size: tuple = (8, 8), padding_size=(0, 0, 0, 0),
                 steps=50, debug_root="./Data/Debug/", alpha=5, plot_interval=10):
        """
        Base class to implement various attacks
        :param objective_image: image to attack
        :param objective_mask: binary mask of the image to attack, 0 = authentic, 1 = forged
        :param image_path: path to the image's file
        :param mask_path: path to the image's mask's file
        :param qf: quality factor to use
        :param patch_size: size of the patch ot use to generate the target representation
        :param steps: total number of steps of the attack
        :param debug_root: root dolder in which save debug data generated by the attack
        """

        self.padding_size = padding_size

        super().__init__("LOTS4Noiseprint_3", objective_image, objective_mask, target_representation_image,
                         target_representation_mask, qf, patch_size, steps,
                         debug_root, alpha, plot_interval)

    def _generate_target_representation(self, image: Picture, mask: Picture):
        """
        Generate the target representation executing the following steps:

            1) Generate an image wise noiseprint representation on the entire image
            2) Divide this noiseprint map into patches
            3) Average these patches
            4) Create an image wide target representation by tiling these patches together

        :return: the target representation in the shape of a numpy array
        """

        authentic_patches = image.get_authentic_patches(mask, self.patch_size, self.padding_size,
                                                        force_shape=True,
                                                        zero_padding=True)

        complete_patch_size = (self.patch_size[0] + self.padding_size[1] + self.padding_size[3],
                               self.patch_size[1] + self.padding_size[0] + self.padding_size[2])

        # create target patch object
        target_patch = np.zeros(complete_patch_size)

        patches_map = np.zeros(image.shape)

        # generate authentic target representation
        self.write_to_logs("Generating target representation...", logging.INFO)
        for original_patch in tqdm(authentic_patches):
            assert (original_patch.shape == target_patch.shape)

            noiseprint_patch = np.squeeze(self._engine._model(original_patch[np.newaxis, :, :, np.newaxis]))

            target_patch += noiseprint_patch / len(authentic_patches)

            patches_map = original_patch.no_paddings().add_to_image(patches_map)

        self.write_to_logs("Target representation generated", logging.INFO)

        target_patch = authentic_patches[0].no_paddings(target_patch)

        # compute the tiling factors along the X and Y axis
        repeat_factors = (ceil(image.shape[0] / target_patch.shape[0]), ceil(image.shape[1] / target_patch.shape[1]))

        # tile the target representations together
        image_target_representation = np.tile(target_patch, repeat_factors)

        # cut away "overflowing" margins
        image_target_representation = image_target_representation[:image.shape[0], :image.shape[1]]

        # save tile visualization
        visuallize_array_values(target_patch, os.path.join(self.debug_folder, "image-target-raw.png"))

        patches_map = Picture(normalize_noiseprint(patches_map))
        patches_map.save(os.path.join(self.debug_folder, "patches-map.png"))

        image_wide_representation = Picture(normalize_gradient(image_target_representation, margin=0))
        image_wide_representation.save(os.path.join(self.debug_folder, "image-wide-target-map.png"))

        return image_target_representation

    def _get_gradient_of_image(self, image: Picture, target: Picture):
        """
        Perform step of the attack executing the following steps:

            1) Divide the entire image into patches
            2) Compute the gradient of each patch with respect to the patch-tirget representation
            3) Recombine all the patch-gradients to obtain a image wide gradient
            4) Apply the image-gradient to the image
        :return: image_gradient, cumulative_loss
        """

        assert (len(image.shape) == 2)

        # variable to store the cumulative loss across all patches
        cumulative_loss = 0

        # image wide gradient
        image_gradient = np.zeros(image.shape)

        if image.shape[0] * image.shape[1] < NoiseprintEngine.large_limit:
            # the image can be processed as a single patch
            image_gradient, cumulative_loss = self._get_gradient_of_patch(Patch(image), target)

        else:
            # the image is too big, we have to divide it in patches to process separately
            # iterate over x and y, strides = self.slide, window size = self.slide+2*self.overlap
            for x in range(0, image.shape[0], self._engine.slide):
                x_start = x - self._engine.overlap
                x_end = x + self._engine.slide + self._engine.overlap
                for y in range(0, image.shape[1], self._engine.slide):
                    y_start = y - self._engine.overlap
                    y_end = y + self._engine.slide + self._engine.overlap

                    # get the patch we are currently working on
                    patch = image[
                            max(x_start, 0): min(x_end, image.shape[0]),
                            max(y_start, 0): min(y_end, image.shape[1])
                            ]

                    # get the desired target representation for this patch
                    target_patch = target[
                                   max(x_start, 0): min(x_end, image.shape[0]),
                                   max(y_start, 0): min(y_end, image.shape[1])
                                   ]

                    print(patch.shape, target_patch.shape)
                    patch_gradient, patch_loss = self._get_gradient_of_patch(patch, target_patch)

                    # discard initial overlap if not the row or first column
                    if x > 0:
                        patch_gradient = patch_gradient[self._engine.overlap:, :]
                    if y > 0:
                        patch_gradient = patch_gradient[:, self._engine.overlap:]

                    # add this patch loss to the total loss
                    cumulative_loss += patch_loss

                    # add this patch's gradient to the image gradient
                    # discard data beyond image size
                    patch_gradient = patch_gradient[:min(self._engine.slide, patch.shape[0]),
                                     :min(self._engine.slide, patch.shape[1])]

                    # copy data to output buffer
                    image_gradient[x: min(x + self._engine.slide, image_gradient.shape[0]),
                    y: min(y + self._engine.slide, image_gradient.shape[1])] = patch_gradient

        return image_gradient, cumulative_loss

    def _on_before_attack_step(self):
        """
        Check that the attack can be executed, if not, generate a target representation
        and execute it
        :return:
        """
        print("### Step:{} ###".format(self.attack_iteration))
        # if no target representation is present, generate it
        if self.target_representation is None:
            self._generate_target_representation()

        super()._on_before_attack_step()
