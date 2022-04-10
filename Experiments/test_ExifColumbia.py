from Datasets.ColumbiaUncompressed.ColumbiaUncompressedDataset import ColumbiaUncompressedDataset
from Utilities.Confs.Configs import Configs
from Attacks.Exif.Mimicking.ExifMimickingIntelligentAttack import ExifIntelligentAttack
from Utilities.Experiments.Attacks.ExifExperiment import ExifExperiment
from Utilities.Logger.Logger import setup_logging

configs = Configs("../config.yaml", "Exif-Columbia")

possible_forgery_masks = {
    "300x300":[
        "./Data/custom/target_forgery_masks/DSO/1.png",
        "./Data/custom/target_forgery_masks/DSO/2.png",
        "./Data/custom/target_forgery_masks/DSO/3.png"
    ],
    "150x150": [
        "./Data/custom/target_forgery_masks/COLUMBIA/1.png",
        "./Data/custom/target_forgery_masks/COLUMBIA/2.png",
        "./Data/custom/target_forgery_masks/COLUMBIA/3.png"
    ]
}

root_experiment = configs.debug_root

attack = ExifIntelligentAttack(50, 5, plot_interval=-1, verbosity=0, debug_root=configs.create_debug_folder("executions"))

dataset = ColumbiaUncompressedDataset(configs["global"]["datasets"]["root"])

experiment = ExifExperiment(attack, dataset, possible_forgery_masks, configs.create_debug_folder("outputs"),False)

experiment.execute()
