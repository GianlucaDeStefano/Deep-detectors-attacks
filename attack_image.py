import argparse
import os

from Attacks import families_of_attacks

DEBUG_ROOT = os.path.abspath("Data/Debug/")
DATASETS_ROOT = os.path.abspath("Data/Datasets/")


def attack_pipeline(category_number, attack_number):

    if category_number is None:

        c = 0
        for key, supported_attack in families_of_attacks.items():
            print("  {}) {}".format(c, key))
            c = c + 1
        category_number = int(input("Enter category number:"))


    supported_attacks = list(families_of_attacks.values())[category_number]

    if attack_number is None:
        i = 0
        for key, supported_attack in supported_attacks.items():
            print("  {}) {}".format(i, key))
            i = i + 1
        print("  {}) {}".format(i, "All attacks in sequence"))
        attack_number = int(input("Enter attack number:"))

    if attack_number == len(supported_attacks.items()):
        attacks = supported_attacks.values()
    else:
        attacks = list(supported_attacks.values())[attack_number]

    if not isinstance(attacks, list):
        attacks = [attacks]

    # execute each attack sequentially
    for current_attack in attacks:
        kwarg = current_attack.read_arguments(DATASETS_ROOT)

        attack = current_attack(**kwarg)
        attack.execute()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", '--type', default=None, type=int,help='Id of the category of the attack to perform')
    parser.add_argument("-m", '--method', default=None, type=int,help='Id of the attack to perform')
    args = parser.parse_known_args()[0]

    attack_pipeline(args.type,args.method)
