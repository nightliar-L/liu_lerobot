#!/usr/bin/env python

# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
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
from typing import Iterator, Union

import torch


class EpisodeAwareSampler:
    def __init__(
        self,
        episode_data_index: dict,
        episode_indices_to_use: Union[list, None] = None,
        drop_n_first_frames: int = 0,
        drop_n_last_frames: int = 0,
        shuffle: bool = True,
    ):
        """Sampler that optionally incorporates episode boundary information.

        Args:
            episode_data_index (dict): Dictionary with keys 'from' and 'to' containing the start and end indices of each episode.
            episode_indices_to_use (list, optional): List of episode indices to use. If None, all episodes are used. Defaults to None.
                                                     Assumes that episodes are indexed from 0 to N-1.
            drop_n_first_frames (int, optional): Number of frames to drop from the start of each episode. Defaults to 0.
            drop_n_last_frames (int, optional): Number of frames to drop from the end of each episode. Defaults to 0.
            shuffle (bool, optional): Whether to shuffle the indices. Defaults to True.
        """
        indices = []
        for episode_idx, (start_index, end_index) in enumerate(
            zip(episode_data_index["from"], episode_data_index["to"], strict=True)
        ):
            if episode_indices_to_use is None or episode_idx in episode_indices_to_use:
                indices.extend(
                    range(start_index.item() + drop_n_first_frames, end_index.item() - drop_n_last_frames)
                )

        self.indices = indices
        self.shuffle = shuffle

    def __iter__(self) -> Iterator[int]:
        if self.shuffle:
            for i in torch.randperm(len(self.indices)):
                yield self.indices[i]
        else:
            for i in self.indices:
                yield i

    def __len__(self) -> int:
        return len(self.indices)
