import os
from pathlib import Path

import numpy as np
from PIL.Image import Image

from Datasets.Dataset import Dataset, ImageNotFoundException


def mask_2_binary(mask: np.array):
    """
    Convert a mask of the Columbia Uncompressed dataset to a Binary mask
    :param mask:
    :return: binary mask
    """

    mask = np.asarray(mask, dtype="int32")

    # transform the mask into a binary mask:

    mask = mask[:, :, 0]
    return np.where(mask != 0, 0, 1)


class ColumbiaUncompressedDataset(Dataset):

    def __init__(self, root=os.path.dirname(__file__) + "/Data/"):
        super(ColumbiaUncompressedDataset, self).__init__(root, False, ["tif"])

    def get_authentic_images(self, target_shape=None):
        """
        Return a list of paths to all the authentic images
        :param root: root folder of the dataset
        :return: list of Paths
        """

        paths = []

        for image_format in self.supported_formats:
            paths += Path(os.path.join(self.root, "4cam_auth")).glob("*.{}".format(image_format))

        return paths

    def get_forged_images(self, target_shape=None):
        """
        Return a list of paths to all the authentic images
        :param root: root folder of the dataset
        :return: list of Paths
        """

        paths = []

        for image_format in self.supported_formats:
            Path(os.path.join(self.root, "4cam_splc")).glob("*.{}".format(image_format))

        return paths

    def get_mask_of_image(self, image_path: str):

        filename = os.path.basename(image_path)
        filename = os.path.splitext(filename)[0] + "_edgemask.tif"

        image_path = Path(image_path)

        mask = Image.open(os.path.join(image_path.parent, 'edgemask', filename))
        mask.load()

        return mask_2_binary(mask)

    def get_image(self, image_name):
        if Path(os.path.join(self.root, "4cam_splc",image_name)).exists():
            return image_name
        else:
            raise ImageNotFoundException(image_name)