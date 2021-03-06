# coding=utf-8
# Copyright 2020 The Google AI Perception Team Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Estimate AIST++ camera parameters."""
import json
import math
import os
import random

from absl import app
from absl import flags
from aist_plusplus.loader import AISTDataset
import aniposelib
import numpy as np

FLAGS = flags.FLAGS
flags.DEFINE_string(
    'anno_dir',
    '/usr/local/google/home/ruilongli/data/public/aist_plusplus_final/',
    'input local dictionary for AIST++ annotations.')
flags.DEFINE_string(
    'save_dir',
    '/usr/local/google/home/ruilongli/data/public/aist_plusplus_final/cameras/',
    'output local dictionary that stores AIST++ camera parameters.')
random.seed(0)
np.random.seed(0)


def init_env_cameras():
  """Trys to estimate the environment manually."""
  cams = []
  for i, view in enumerate(AISTDataset.VIEWS):
    f = 1600
    cx = 1920 // 2
    cy = 1080 // 2
    if view == 'c09':
      rvec = [0, -math.radians(0), 0]
      tvec = [0, -170, -500]
    else:
      rvec = [0, -math.radians(360 // 8 * i), 0]
      tvec = [0, -180, -500]

    matrix = np.array([
        [f, 0, cx],
        [0, f, cy],
        [0, 0, 1],
    ], dtype=np.float32)
    cams.append(
        aniposelib.cameras.Camera(
            matrix=matrix, rvec=rvec, tvec=tvec, name=view, size=(1920, 1080)))
  cgroup = aniposelib.cameras.CameraGroup(cams)
  return cgroup


def main(_):
  aist_dataset = AISTDataset(anno_dir=FLAGS.anno_dir)

  for env_name, seq_names in aist_dataset.mapping_env2seq.items():
    # Init camera parameters
    cgroup = init_env_cameras()

    # Select a set of sequences for optimizing camera parameters.
    seq_names = random.choices(seq_names, k=20)

    # Load 2D keypoints
    keypoints2d_all = []
    for seq_name in seq_names:
      keypoints2d_raw, _, _ = AISTDataset.load_keypoint2d(
          aist_dataset.keypoint2d_dir, seq_name=seq_name)
      # Special cases
      if seq_name == 'gBR_sBM_cAll_d04_mBR0_ch01':
        keypoints2d_raw[4] = np.nan  # not synced view
      if seq_name == 'gJB_sBM_cAll_d07_mJB3_ch05':
        keypoints2d_raw[6] = np.nan  # size 640x480
      keypoints2d_all.append(keypoints2d_raw)
    keypoints2d_all = np.concatenate(keypoints2d_all, axis=1)

    # Filter keypoints to select those best points
    kpt_thre = 0.5
    ignore_idxs = np.where(keypoints2d_all[:, :, :, 2] < kpt_thre)
    keypoints2d_all[ignore_idxs[0], ignore_idxs[1], ignore_idxs[2], :] = np.nan
    keypoints2d_all = keypoints2d_all[..., 0:2]

    # Apply bundle adjustment and dump the camera parameters
    nviews = keypoints2d_all.shape[0]
    cgroup.bundle_adjust_iter(
        keypoints2d_all.reshape(nviews, -1, 2),
        n_iters=20,
        n_samp_iter=500,
        n_samp_full=5000,
        verbose=True)
    os.makedirs(FLAGS.save_dir, exist_ok=True)
    camera_file = os.path.join(FLAGS.save_dir, f'{env_name}.json')
    with open(camera_file, 'w') as f:
      json.dump([camera.get_dict() for camera in cgroup.cameras], f)


if __name__ == '__main__':
  app.run(main)
