import os.path
from abc import ABC, abstractmethod

import os.path
from abc import ABC, abstractmethod

import cv2
import numpy as np
import tensorflow as tf
from matplotlib import pyplot as plt

from Attacks.Lots.BaseLotsAttack import BaseLotsAttack
from Attacks.utilities.image import normalize_noiseprint_no_margins
from Attacks.utilities.visualization import visualize_noiseprint_step
from Detectors.Noiseprint.Noiseprint.noiseprint import NoiseprintEngine, normalize_noiseprint
from Detectors.Noiseprint.Noiseprint.noiseprint_blind import noiseprint_blind_post, genMappFloat
from Detectors.Noiseprint.Noiseprint.utility.utility import jpeg_quality_of_file
from Ulitities.Image.Patch import Patch
from Ulitities.Image.Picture import Picture
from Ulitities.Plots import plot_graph


class MissingTargetRepresentation(Exception):
    def __init__(self, image_name):
        super().__init__("No image found with name: {}".format(image_name))


def normalize_gradient(gradient, margin=17):
    """
    Normalize the gradient cutting away the values on the borders
    :param margin: margin to use along the bordes
    :param gradient: gradient to normalize
    :return: normalized gradient
    """

    # set to 0 part of the gradient too near to the border
    if margin > 0:
        gradient[0:margin, :] = 0
        gradient[-margin:, :] = 0
        gradient[:, 0:margin] = 0
        gradient[:, -margin:] = 0

    # scale the final gradient using the computed infinity norm
    gradient = gradient / np.max(np.abs(gradient))
    return gradient


class Lots4NoiseprintBase(BaseLotsAttack, ABC):

    def __init__(self,name: str, objective_image: Picture, objective_mask: Picture, target_representation_image: Picture = None,
                 target_representation_mask: Picture = None, qf: int = None,
                 patch_size: tuple = (8, 8), steps=50,
                 debug_root="./Data/Debug/", alpha=5, plot_interval=3):
        """
        Base class to implement various attacks
        :param objective_image: image to attack
        :param objective_mask: binary mask of the image to attack, 0 = authentic, 1 = forged
        :param name: name to identify the attack
        :param qf: quality factor to use
        :param patch_size: size of the patch ot use to generate the target representation
        :param steps: total number of steps of the attack
        :param debug_root: root folder in which save debug data generated by the attack
        """

        # check the passe patch is not too wide for be handled by noiseprint
        assert (patch_size[0] * patch_size[1] < NoiseprintEngine.large_limit)

        super().__init__(name,objective_image, objective_mask, target_representation_image, target_representation_mask,
                         patch_size, steps, debug_root, alpha,
                         plot_interval)

        if not qf or  qf < 51 or qf > 101:
            try:
                qf = jpeg_quality_of_file(objective_image.path)
            except:
                qf = 101

        # save the parameters of noiseprint
        self.qf = qf
        self._engine = NoiseprintEngine()
        self._engine.load_quality(qf)

        self.loss_steps = []
        self.psnr_steps = []
        self.noiseprint_variance_steps = []

        self.min_loss = float("inf")

    def _on_after_attack_step(self):

        # compute PSNR between intial 1 channel image and the attacked one
        psnr = cv2.PSNR(self.objective_image.one_channel, self.attacked_image_one_channel)
        self.psnr_steps.append(psnr)

        # compute variance on the noiseprint map
        image = self.objective_image.to_float().one_channel + self.adversarial_noise
        noiseprint = self._engine.predict(image)
        self.noiseprint_variance_steps.append(noiseprint.var())

        super()._on_after_attack_step()

        plot_graph(self.loss_steps, "Loss", os.path.join(self.debug_folder, "loss"))
        plot_graph(self.psnr_steps, "PSNR", os.path.join(self.debug_folder, "psnr"))
        plot_graph(self.noiseprint_variance_steps, "Variance", os.path.join(self.debug_folder, "variance"))

        if self.loss_steps[-1] < self.min_loss:
            self.min_loss = self.loss_steps[-1]

            self.best_noise = self.adversarial_noise

            # Log
            self.write_to_logs(
                "New optimal noise found, saving it to :{}".format(os.path.join(self.debug_folder, 'best-noise.npy')))

            # save the best adversarial noise
            np.save(os.path.join(self.debug_folder, 'best-noise.npy'), self.adversarial_noise)



    def plot_step(self,image):

        noiseprint = self._engine.predict(image)

        self.noiseprint_variance_steps.append(noiseprint.var())

        mapp, valid, range0, range1, imgsize, other = noiseprint_blind_post(noiseprint, image)
        attacked_heatmap = genMappFloat(mapp, valid, range0, range1, imgsize)

        magnified_noise = normalize_gradient(self.adversarial_noise.three_channel, 0)

        visualize_noiseprint_step(self.attacked_image.to_float(), normalize_noiseprint(noiseprint),
                                  magnified_noise,
                                  attacked_heatmap,
                                  os.path.join(self.debug_folder, "Steps", str(self.attack_iteration)))

    def _on_after_attack(self):
        """
        Function executed after finishing the attack pipeline
        :return:
        """

        super()._on_after_attack()
        image_path = os.path.join(self.debug_folder, "attacked image best noise.png")

        best_attacked_image = Picture((self.objective_image - Picture(self.best_noise).three_channel).clip(0,255))
        best_attacked_image.save(image_path)

        # generate heatmap of the just saved image, just to be sure of the final result of the attack
        image = Picture(path=image_path)
        noiseprint = self._engine.predict(image.to_float().one_channel)

        mapp, valid, range0, range1, imgsize, other = noiseprint_blind_post(noiseprint, image.to_float().one_channel)
        attacked_heatmap = genMappFloat(mapp, valid, range0, range1, imgsize)

        magnified_noise = normalize_noiseprint(image - self.objective_image)

        visualize_noiseprint_step(image.to_float(), normalize_noiseprint(noiseprint), magnified_noise,
                                  attacked_heatmap, os.path.join(self.debug_folder, "final attack"))


    def _get_gradient_of_patch(self, image_patch: Patch, target):
        """
        Compute gradient of the patch
        :param image_patch:
        :param target:
        :return:
        """

        assert (image_patch.shape == target.shape)

        # be sure that the given patch and target are of the same shape
        with tf.GradientTape() as tape:
            tensor_patch = tf.convert_to_tensor(image_patch[np.newaxis, :, :, np.newaxis])
            tape.watch(tensor_patch)

            # perform feed foward pass
            patch_noiseprint = tf.squeeze(self._engine._model(tensor_patch))

            # compute the loss with respect to the target representation
            loss = tf.nn.l2_loss(target - patch_noiseprint)

            # retrieve the gradient of the patch
            patch_gradient = np.squeeze(tape.gradient(loss, tensor_patch).numpy())

            # check that the retrieved gradient has the correct shape
            assert (patch_gradient.shape == image_patch.shape)

            return patch_gradient, loss

    @abstractmethod
    def _get_gradient_of_image(self, image: Picture, target: Picture):
        """
        Compute the gradient for the entire image
        :param image: image for which we have to compute the gradient
        :param target: target to use
        :return: numpy array containing the gradient
        """

        raise NotImplemented

    def _attack_step(self):
        """
        Perform step of the attack executing the following steps:

            1) Divide the entire image into patches
            2) Compute the gradient of each patch with respect to the patch-tirget representation
            3) Recombine all the patch-gradients to obtain a image wide gradient
            4) Apply the image-gradient to the image
            5) Convert then the image to the range of values of integers [0,255] and convert it back to the range
               [0,1]
        :return:
        """
        # compute the gradient
        image_gradient, loss = self._get_gradient_of_image(self.attacked_image_one_channel.to_float(),
                                                           self.target_representation)

        # save loss value to plot it
        self.loss_steps.append(loss)

        # normalize the gradient
        image_gradient = normalize_gradient(image_gradient, 8)

        # scale the gradient
        image_gradient = self.alpha * image_gradient

        # add noise
        self.adversarial_noise_array += image_gradient

    def _log_step(self) -> str:
        "Generate the logging to write at each step"
        return " {}) Duration: {} Loss:{} BestLoss:{}".format(self.attack_iteration,
                                                              self.end_step_time - self.start_step_time,
                                                              self.loss_steps[-1], min(self.loss_steps))

    @abstractmethod
    def _generate_target_representation(self, image: Picture, mask: Picture):
        raise NotImplemented
