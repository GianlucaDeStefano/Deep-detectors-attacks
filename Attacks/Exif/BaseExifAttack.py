from abc import ABC

import numpy as np
import tensorflow as tf
from Attacks.BaseWhiteBoxAttack import BaseWhiteBoxAttack
from Detectors.Exif.ExifEngine import ExifEngine
from Detectors.Exif.lib.utils import ops
from Detectors.Exif.models.exif import exif_net
from Ulitities.Image.Picture import Picture


class BaseExifAttack(BaseWhiteBoxAttack, ABC):
    """
        This class is used to implement white box attacks on the Exif-Sc detector
    """

    def __init__(self, target_image: Picture, target_image_mask: Picture, source_image: Picture,
                 source_image_mask: Picture, steps: int, alpha: float,
                 regularization_weight=0.05, plot_interval=5, patch_size=(128, 128), batch_size: int = 64,
                 debug_root: str = "./Data/Debug/", test: bool = True):
        """
        :param target_image: original image on which we should perform the attack
        :param target_image_mask: original mask of the image on which we should perform the attack
        :param source_image: image from which we will compute the target representation
        :param source_image_mask: mask of the imae from which we will compute the target representation
        :param steps: number of attack iterations to perform
        :param alpha: strength of the attack
        :param regularization_weight: [0,1] importance of the regularization factor in the loss function
        :param plot_interval: how often (# steps) should the step-visualizations be generated?
        :param patch_size: Width and Height of the patches we are using to compute the Exif parameters
                            we assume that the the patch is always a square eg patch_size[0] == patch_size[1]
        :param batch_size: how many patches shall be processed in parallel
        :param debug_root: root folder inside which to create a folder to store the data produced by the pipeline
        :param test: is this a test mode? In test mode visualizations and superfluous steps will be skipped in favour of a
            faster execution to test the code
        """

        super().__init__(target_image, target_image_mask, source_image, source_image_mask, "Exif", steps, alpha, 0.5,
                         regularization_weight,
                         plot_interval, True, debug_root, test)

        assert (patch_size[0] == patch_size[1])
        self.batch_size = batch_size

        self.patch_size = patch_size

        self._engine = self.detector._engine.model.solver.net
        self._sess = self.detector._engine.model.solver.sess

        self.moving_avg_gradient = np.zeros(target_image.shape)
        self.noise = np.zeros(target_image.shape)

        self.get_gradient = self._get_gradient_of_batch

        self.x = tf.compat.v1.placeholder(tf.float32, shape=[None, 128, 128, 3])
        self.y = tf.compat.v1.placeholder(tf.float32, shape=[None, 4096])

        self.gradient_op = None
        self.loss_op = None

    def _on_before_attack(self):
        """
        Populate the gradent_op and loss_op variables
        :return:
        """

        super()._on_before_attack()

        with self._sess.as_default():
            self.gradient_op, self.loss_op = self._get_gradient_of_batch()

    def _get_gradient_of_batch(self):
        """
        Given a list of patches ready to be processed and their target representation, compute the gradient w.r.t the
        specified loss
        :param x: list of patches to process (len(batch_patches) must be equal to
            self.batch_size)
        :param y: list of target representations (len(target_batch_patches) must
            be equal to self.batch_size)
        :param regularization_value: regularizataion value that will be applied to the loss function
        :return: return a list of gradients (one per patch) and the cumulative loss
        """

        # perform feed forward pass
        feature_representation = self._engine.extract_features_resnet50(self.x, "test", reuse=True)

        # compute the loss with respect to the target representation
        loss = tf.norm(feature_representation - self.y, 2)

        # construct the gradients object
        gradients = tf.gradients(loss, self.x)

        return gradients, loss
