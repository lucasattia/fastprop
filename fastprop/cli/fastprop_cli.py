import argparse
import json
import sys
from importlib.metadata import version

import yaml

from fastprop import DEFAULT_TRAINING_CONFIG, hopt_fastprop, train_fastprop
from fastprop.defaults import init_logger
from fastprop.utils import validate_config

logger = init_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="fastprop command line interface - try 'fastprop subcommand --help'")

    parser.add_argument("-v", "--version", help="print version and exit", action="store_true")

    subparsers = parser.add_subparsers(dest="subcommand")

    train_subparser = subparsers.add_parser("train")
    train_subparser.add_argument("config_file", nargs="?", help="YAML configuration file")
    train_subparser.add_argument("-od", "--output-directory", help="directory for fastprop output")
    # featurization
    train_subparser.add_argument("-if", "--input-file", help="csv of SMILES and targets")
    train_subparser.add_argument("-tc", "--target-columns", nargs="+", help="column name(s) for target(s)")
    train_subparser.add_argument("-sc", "--smiles-column", help="column name for SMILES")
    train_subparser.add_argument("-d", "--descriptors", help="descriptors to calculate (one of all, optimized, smallest, or search)")
    train_subparser.add_argument("-ec", "--enable-cache", type=bool, help="allow saving and loading of cached descriptors")
    train_subparser.add_argument("-p", "--precomputed", help="precomputed descriptors from fastprop or mordred")

    # preprocessing
    train_subparser.add_argument("-r", "--rescaling", type=bool, help="rescale descriptors between 0 and 1 (default to True)")
    train_subparser.add_argument("-zvd", "--zero-variance-drop", type=bool, help="drop zero variance descriptors (defaults to True)")
    train_subparser.add_argument("-cd", "--colinear-drop", type=bool, help="drop colinear descriptors (defaults to False)")

    # training
    train_subparser.add_argument("-op", "--optimize", action="store_true", help="run hyperparameter optimization", default=False)
    train_subparser.add_argument("-fl", "--fnn-layers", type=int, help="number of fnn layers")
    train_subparser.add_argument("-lr", "--learning-rate", type=float, help="learning rate")
    train_subparser.add_argument("-bs", "--batch-size", type=int, help="batch size")
    train_subparser.add_argument("-ne", "--number-epochs", type=int, help="number of epochs")
    train_subparser.add_argument("-nr", "--number-repeats", type=int, help="number of repeats")
    train_subparser.add_argument("-pt", "--problem-type", help="problem type (regression or a type of classification)")
    train_subparser.add_argument("-ns", "--train-size", help="train size")
    train_subparser.add_argument("-vs", "--val-size", help="val size")
    train_subparser.add_argument("-ts", "--test-size", help="test size")
    train_subparser.add_argument("-s", "--sampler", help="choice of sampler, i.e. random, kmeans, etc.")
    train_subparser.add_argument("-rs", "--random-seed", help="random seed for sampling and pytorch seed")
    train_subparser.add_argument("-pc", "--patience", help="number of epochs to wait before early stopping")

    predict_subparser = subparsers.add_parser("predict")
    predict_subparser.add_argument("-cd", "--checkpoints_dir", required=True, help="directory of checkpoint file(s) for predictions")
    input_group = predict_subparser.add_mutually_exclusive_group()
    input_group.add_argument("-s", "--smiles", help="SMILES string for prediction")
    input_group.add_argument("-i", "--input-file", help="file containing SMILES strings")
    predict_subparser.add_argument("-o", "--output", required=False, help="output file for predictions (defaults to stdout)")

    # no args provided - print the help text
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if args.version:
        print(version("fastprop"))
        exit(0)

    # cast to a dict
    args = vars(args)
    subcommand = args.pop("subcommand")
    args.pop("version")
    if subcommand == "train":
        training_default = dict(DEFAULT_TRAINING_CONFIG)
        # exit with help if no args given
        if not sum(map(lambda i: i is not None, args.values())):
            train_subparser.print_help()
            exit(0)
        optim_requested = args.pop("optimize")
        if args["config_file"] is not None:
            if sum(map(lambda i: i is not None, args.values())) > 1:
                raise parser.error("Cannot specify config_file with other command line arguments (except --optimize).")
            with open(args["config_file"], "r") as f:
                cfg = yaml.safe_load(f)
                cfg["target_columns"] = cfg["target_columns"].split(" ")
                training_default.update(cfg)
        else:
            training_default.update({k: v for k, v in args.items() if v is not None})

        optim_requested = training_default.pop("optimize") or optim_requested
        logger.info(f"Training Parameters:\n {json.dumps(training_default, indent=4)}")
        # validate this dictionary, i.e. layer counts are positive, etc.
        # cannot specify both precomputed and descriptors or enable/cache
        validate_config(training_default)
        if optim_requested:
            training_default.pop("fnn_layers")
            training_default.pop("hidden_size")
            if any((args.get("fnn_layers") is not None, args.get("hidden_size") is not None)):
                logger.warning("Hidden Size/FNN Layers specified with optimize and are ignored.")
            hopt_fastprop(**training_default)
        else:
            train_fastprop(**training_default)
    else:
        if args["smiles"] is None and args["input_file"] is None:
            raise parser.error("One of -i/--input-file or -s/--smiles must be provided.")
        logger.info(f"Predict Parameters:\n {json.dumps(args, indent=4)}")
