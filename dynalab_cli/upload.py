# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
import shutil
import subprocess
import tempfile

import requests
import json

from dynalab.config import DYNABENCH_API
from dynalab_cli import BaseCommand
from dynalab_cli.utils import AccessToken, SetupConfigHandler


class UploadCommand(BaseCommand):
    @staticmethod
    def add_args(parser):
        upload_parser = parser.add_parser(
            "upload", help="User Upload and authentication"
        )
        upload_parser.add_argument(
            "-n", "--name", type=str, required=True, help="Name of the model"
        )

    def __init__(self, args):
        self.args = args
        self.config_handler = SetupConfigHandler(args.name)

    def run_command(self):
        # validate config
        try:
            self.config_handler.validate_config()
        except AssertionError as err:
            print(
                f"Error: {err}.\nPlease fix your config file by",
                "dynalab-cli init --amend",
            )
            exit(1)
        else:
            config = self.config_handler.load_config()
            print("Config file validated")

        # set up exclude files for tarball
        print("Tarballing the project directory...")
        tmp_dir = os.path.join(".dynalab", self.args.name, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        exclude_list_file = os.path.join(tmp_dir, "exclude.txt")
        self.config_handler.write_exclude_filelist(
            exclude_list_file, self.args.name, exclude_model=False
        )

        # tarball
        tmp_tarball_dir = tempfile.TemporaryDirectory()
        tarball = os.path.join(tmp_tarball_dir.name, f"{self.args.name}.tar.gz")
        process = subprocess.run(
            ["tar", f"--exclude-from={exclude_list_file}", "-czf", tarball, "."],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"Error in tarballing the current directory {process.stderr}"
            )
        # upload to s3
        print("Uploading file to S3...")
        url = f"{DYNABENCH_API}/models/upload/s3"
        task_code = config["task"]
        auth_header = AccessToken().get_headers()["Authorization"]
        res = subprocess.check_output(
            [
                "curl",
                "--verbose",
                "-H",
                "Content-Type: multipart/form-data",
                "-H",
                f"Authorization: {auth_header}",
                "-F",
                f"name={self.args.name}",
                "-F",
                f"taskCode={task_code}",
                "-F",
                f"tarball=@{tarball}",
                url,
            ]
        )
        if res:
            error = json.loads(res).get("error")
            assert not error, error

        # TODO: show which email address it is: API to fetch email address?
        print(
            f"Your model {self.args.name} has been uploaded to S3 and "
            f"will be deployed shortly. "
            f"You will get an email notification when your model is available "
            f"on Dynabench."
        )
