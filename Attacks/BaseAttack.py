import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
import numpy as np
from PIL import Image

import logging

from tqdm import tqdm

from Ulitities.Image import Picture


class BaseAttack(ABC):

    def __init__(self,name: str, objective_image: Picture, objective_mask: Picture,steps=50,
                 debug_root="./Data/Debug/", plot_interval=3):
        """
        Base class to implement various attacks
        :param objective_image: image to attack
        :param objective_mask: binary mask of the image to attack, 0 = authentic, 1 = forged
        :param name: name to identify the attack
        :param steps: total number of steps of the attack
        :param debug_root: root folder in which save debug data generated by the attack
        :param plot_interval: frequency at which printing an extensive plot of a step
        """

        assert (objective_image.shape[0] == objective_mask.shape[0])
        assert (objective_image.shape[1] == objective_mask.shape[1])

        self.objective_image = objective_image
        self.objective_image_mask = objective_mask
        self.attack_iteration = 0
        self.name = name
        self.steps = steps
        self.debug_folder = debug_root
        self.plot_interval = plot_interval

        self.best_noise = np.zeros(self.objective_image.one_channel.shape)
        self.adversarial_noise_array = np.zeros(self.objective_image.one_channel.shape)

        times = time.time()
        self.debug_folder = os.path.join(debug_root, str(times))
        os.makedirs(self.debug_folder)
        os.makedirs(os.path.join(self.debug_folder, "Steps"))
        logging.basicConfig(format='%(message)s', filename=os.path.join(self.debug_folder, "logs.txt"),
                            level=logging.DEBUG)

        for name in logging.root.manager.loggerDict:
            logging.getLogger(name).disabled = True

    def attack_one_step(self):
        """
        Perform one step of the attack
        :return:
        """

        self._on_before_attack_step()
        self._attack_step()
        self._on_after_attack_step()

        return self.attacked_image

    def execute(self):
        """
        Launch the entire attack pipeline
        :return:
        """
        start_time = datetime.now()
        self.write_to_logs("Starting attack pipeline")

        self._on_before_attack()

        for self.attack_iteration in range(self.steps):
            print("### Step: {} ###".format(self.attack_iteration))
            self.attack_one_step()

        self._on_after_attack()

        end_time = datetime.now()
        timedelta = end_time - start_time
        self.write_to_logs(
            "Attack pipeline terminated in {}".format(timedelta))

    @abstractmethod
    def _attack_step(self):
        """
        Performs a step of the attack
        """
        raise NotImplemented

    def _on_before_attack(self):
        """
        Function executed before starting the attack pipeline
        :return:
        """

        # save image
        self.objective_image.save(os.path.join(self.debug_folder, "image.png"))

        # save mask
        self.objective_image_mask.to_int().save(os.path.join(self.debug_folder, "mask.png"))

        self.write_to_logs("Attack name: {}".format(self.name))
        self.write_to_logs("Attacking image: {}".format(self.objective_image.path))
        self.write_to_logs("Mask: {}".format(self.objective_image_mask.path))

        self.start_time = datetime.now()
        self.write_to_logs("Attack started at: {}".format(self.start_time))

        self.plot_step(self.attacked_image_one_channel.to_float())


    def _on_after_attack(self):
        """
        Function executed after finishing the attack pipeline
        :return:
        """

        # save the adversarial noise
        np.save(os.path.join(self.debug_folder, 'best-noise.npy'), self.best_noise)

        self.plot_step(self.attacked_image_one_channel.to_float())
        self.end_time = datetime.now()

    def _on_before_attack_step(self):
        """
        Function executed before starting the i-th attack step
        :return:
        """

        self.start_step_time = datetime.now()

    def _on_after_attack_step(self):
        """
        Function executed after ending the i-th attack step
        :return:
        """

        # log data
        self.end_step_time = datetime.now()
        self.write_to_logs(self._log_step(), False)
        self.attack_iteration += 1

        # generate plots and other visualizations
        if self.attack_iteration % self.plot_interval == 0:
            self.plot_step(self.attacked_image_one_channel.to_float())

        # save the attacked image
        self.attacked_image.save(os.path.join(self.debug_folder, "attacked image.png"))

    @abstractmethod
    def plot_step(self,image):
        """
        Print for debug purposes the state of the attack
        :return:
        """

        if not self.debug_folder:
            return

        raise NotImplemented

    def write_to_logs(self, message, should_print=True):
        """
        Add a new line to this attack's log file IF it exists
        :param message: message to write to the file
        :param level: level of importance of the attack
        :param should_print: should this message be also printed into the console?
        :return:
        """

        if should_print:
            print(message)

        if not self.debug_folder:
            return
        logging.info(message)

    def _log_step(self) -> str:
        "Generate the logging to write at each step"
        return " {}) Duration: {}".format(self.attack_iteration, self.end_step_time - self.start_step_time)

    @property
    def adversarial_noise(self):
        return Picture.Picture(self.adversarial_noise_array,"")

    @property
    def attacked_image_one_channel(self):
        return Picture.Picture(self.objective_image.one_channel - self.adversarial_noise).clip(0, 255)

    @property
    def attacked_image(self):
        return Picture.Picture(self.objective_image - Picture.Picture(self.adversarial_noise).three_channel).clip(0, 255)
