import collections
from typing import Any, Callable, Dict, Sequence

import torch
from torchvision.transforms import v2
from torchvision.transforms.v2 import Transform
from torchvision.transforms.v2 import functional as F  # noqa: N812


class RandomSubsetApply(Transform):
    """
    Apply a random subset of N transformations from a list of transformations.

    Args:
        transforms (sequence or torch.nn.Module): list of transformations
        p (list of floats or None, optional): represents the multinomial probabilities
            (with no replacement) used for sampling the transform. If the sum of the weights is not 1, they
            will be normalized. If ``None`` (default), all transforms have the same probability.
        n_subset (int or None): number of transformations to apply. If ``None``,
            all transforms are applied. Must be in [1, len(transforms)].
        random_order (bool): apply transformations in a random order
    """

    def __init__(
        self,
        transforms: Sequence[Callable],
        p: list[float] | None = None,
        n_subset: int | None = None,
        random_order: bool = False,
    ) -> None:
        super().__init__()
        if not isinstance(transforms, Sequence):
            raise TypeError("Argument transforms should be a sequence of callables")
        if p is None:
            p = [1] * len(transforms)
        elif len(p) != len(transforms):
            raise ValueError(
                f"Length of p doesn't match the number of transforms: {len(p)} != {len(transforms)}"
            )

        if n_subset is None:
            n_subset = len(transforms)
        elif not isinstance(n_subset, int):
            raise TypeError("n_subset should be an int or None")
        elif not (1 <= n_subset <= len(transforms)):
            raise ValueError(f"n_subset should be in the interval [1, {len(transforms)}]")

        self.transforms = transforms
        total = sum(p)
        self.p = [prob / total for prob in p]
        self.n_subset = n_subset
        self.random_order = random_order

    def forward(self, *inputs: Any) -> Any:
        needs_unpacking = len(inputs) > 1

        selected_indices = torch.multinomial(torch.tensor(self.p), self.n_subset)
        if not self.random_order:
            selected_indices = selected_indices.sort().values

        selected_transforms = [self.transforms[i] for i in selected_indices]

        for transform in selected_transforms:
            outputs = transform(*inputs)
            inputs = outputs if needs_unpacking else (outputs,)

        return outputs

    def extra_repr(self) -> str:
        return (
            f"transforms={self.transforms}, "
            f"p={self.p}, "
            f"n_subset={self.n_subset}, "
            f"random_order={self.random_order}"
        )


class SharpnessJitter(Transform):
    """Randomly change the sharpness of an image or video.
    Similar to a v2.RandomAdjustSharpness with p=1 and a sharpness_factor sampled randomly.

    If the input is a :class:`torch.Tensor`,
    it is expected to have [..., 1 or 3, H, W] shape, where ... means an arbitrary number of leading dimensions.

    Args:
        sharpness (float or tuple of float (min, max)): How much to jitter sharpness.
            sharpness_factor is chosen uniformly from [max(0, 1 - sharpness), 1 + sharpness]
            or the given [min, max]. Should be non negative numbers.
    """

    def __init__(self, sharpness: float | Sequence[float]) -> None:
        super().__init__()
        self.sharpness = self._check_input(sharpness)

    def _check_input(self, sharpness):
        if isinstance(sharpness, (int, float)):
            if sharpness < 0:
                raise ValueError("If sharpness is a single number, it must be non negative.")
            sharpness = [1.0 - sharpness, 1.0 + sharpness]
            sharpness[0] = max(sharpness[0], 0.0)
        elif isinstance(sharpness, collections.abc.Sequence) and len(sharpness) == 2:
            sharpness = [float(v) for v in sharpness]
        else:
            raise TypeError(f"{sharpness=} should be a single number or a sequence with length 2.")

        if not 0.0 <= sharpness[0] <= sharpness[1]:
            raise ValueError(f"sharpnesss values should be between (0., inf), but got {sharpness}.")

        return float(sharpness[0]), float(sharpness[1])

    def _generate_value(self, left: float, right: float) -> float:
        return torch.empty(1).uniform_(left, right).item()

    def _transform(self, inpt: Any, params: Dict[str, Any]) -> Any:
        sharpness_factor = self._generate_value(self.sharpness[0], self.sharpness[1])
        return self._call_kernel(F.adjust_sharpness, inpt, sharpness_factor=sharpness_factor)


def get_image_transforms(
    brightness_weight: float = 1.0,
    brightness_min_max: tuple[float, float] | None = None,
    contrast_weight: float = 1.0,
    contrast_min_max: tuple[float, float] | None = None,
    saturation_weight: float = 1.0,
    saturation_min_max: tuple[float, float] | None = None,
    hue_weight: float = 1.0,
    hue_min_max: tuple[float, float] | None = None,
    sharpness_weight: float = 1.0,
    sharpness_min_max: tuple[float, float] | None = None,
    max_num_transforms: int | None = None,
    random_order: bool = False,
):
    def check_value(name, weight, min_max):
        if min_max is not None:
            if len(min_max) != 2:
                raise ValueError(
                    f"`{name}_min_max` is expected to be a tuple of 2 dimensions, but {min_max} provided."
                )
            if weight < 0.0:
                raise ValueError(
                    f"`{name}_weight` is expected to be 0 or positive, but is negative ({weight})."
                )

    check_value("brightness", brightness_weight, brightness_min_max)
    check_value("contrast", contrast_weight, contrast_min_max)
    check_value("saturation", saturation_weight, saturation_min_max)
    check_value("hue", hue_weight, hue_min_max)
    check_value("sharpness", sharpness_weight, sharpness_min_max)

    weights = []
    transforms = []
    if brightness_min_max is not None and brightness_weight > 0.0:
        weights.append(brightness_weight)
        transforms.append(v2.ColorJitter(brightness=brightness_min_max))
    if contrast_min_max is not None and contrast_weight > 0.0:
        weights.append(contrast_weight)
        transforms.append(v2.ColorJitter(contrast=contrast_min_max))
    if saturation_min_max is not None and saturation_weight > 0.0:
        weights.append(saturation_weight)
        transforms.append(v2.ColorJitter(saturation=saturation_min_max))
    if hue_min_max is not None and hue_weight > 0.0:
        weights.append(hue_weight)
        transforms.append(v2.ColorJitter(hue=hue_min_max))
    if sharpness_min_max is not None and sharpness_weight > 0.0:
        weights.append(sharpness_weight)
        transforms.append(SharpnessJitter(sharpness=sharpness_min_max))

    n_subset = len(transforms)
    if max_num_transforms is not None:
        n_subset = min(n_subset, max_num_transforms)

    if n_subset == 0:
        return v2.Identity()
    else:
        # TODO(rcadene, aliberts): add v2.ToDtype float16?
        return RandomSubsetApply(transforms, p=weights, n_subset=n_subset, random_order=random_order)