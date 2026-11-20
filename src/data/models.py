"""Unified data models and integrity validation for CVRP instances."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CVRPInstance:
    """Immutable, validated representation of a CVRP instance.

    Attributes:
        name: Human-readable instance identifier.
        distance_matrix: Square matrix of shape (N, N) with non-negative float64 distances.
        demands: 1D integer array of shape (N,) with node demands (0 at depot).
        capacity: Positive vehicle capacity Q.
        depot: Index of the depot node (default 0).
        coords: Optional (N, 2) Euclidean coordinates.
        latlon: Optional (N, 2) geographic coordinates (latitude, longitude).
        optimal_value: Optional proven optimal total distance.
        node_names: Optional list of N node labels.
    """

    name: str
    distance_matrix: np.ndarray
    demands: np.ndarray
    capacity: int
    depot: int = 0
    coords: np.ndarray | None = None
    latlon: np.ndarray | None = None
    optimal_value: float | None = None
    node_names: list[str] | None = None

    def __post_init__(self) -> None:
        dist = np.asarray(self.distance_matrix, dtype=np.float64)
        dem = np.asarray(self.demands, dtype=np.int64)

        if dist.ndim != 2 or dist.shape[0] != dist.shape[1]:
            raise ValueError(
                f"distance_matrix must be a square 2D array, got shape {dist.shape}"
            )
        n = dist.shape[0]
        if n < 2:
            raise ValueError(
                f"Instance must have at least 2 nodes (depot + >=1 customer), got {n}"
            )
        if not np.all(np.isfinite(dist)):
            raise ValueError("distance_matrix must not contain NaN or infinite values")
        if np.any(dist < 0):
            raise ValueError("distance_matrix must not contain negative distances")

        if dem.ndim != 1 or dem.shape[0] != n:
            raise ValueError(
                f"demands must have shape ({n},) matching distance_matrix, got {dem.shape}"
            )
        if np.any(dem < 0):
            raise ValueError("demands must not contain negative values")

        if not isinstance(self.capacity, (int, np.integer)) or int(self.capacity) <= 0:
            raise ValueError(
                f"capacity must be a positive integer, got {self.capacity}"
            )
        cap = int(self.capacity)

        if not isinstance(self.depot, (int, np.integer)) or not (
            0 <= int(self.depot) < n
        ):
            raise ValueError(f"depot index {self.depot} out of range [0, {n})")
        dep = int(self.depot)

        if dem[dep] != 0:
            raise ValueError(f"depot demand must be 0, got {dem[dep]}")

        if np.any(dem > cap):
            bad = np.where(dem > cap)[0].tolist()
            raise ValueError(
                f"Customer demands at indices {bad} exceed vehicle capacity Q={cap}"
            )

        coords_arr: np.ndarray | None = None
        if self.coords is not None:
            coords_arr = np.asarray(self.coords, dtype=np.float64)
            if coords_arr.shape != (n, 2) or not np.all(np.isfinite(coords_arr)):
                raise ValueError(
                    f"coords must be finite with shape ({n}, 2), got {coords_arr.shape}"
                )
            coords_arr.setflags(write=False)

        latlon_arr: np.ndarray | None = None
        if self.latlon is not None:
            latlon_arr = np.asarray(self.latlon, dtype=np.float64)
            if latlon_arr.shape != (n, 2) or not np.all(np.isfinite(latlon_arr)):
                raise ValueError(
                    f"latlon must be finite with shape ({n}, 2), got {latlon_arr.shape}"
                )
            latlon_arr.setflags(write=False)

        if self.node_names is not None and len(self.node_names) != n:
            raise ValueError(
                f"node_names length ({len(self.node_names)}) must match N={n}"
            )

        if self.optimal_value is not None and self.optimal_value <= 0:
            raise ValueError(
                f"optimal_value must be positive when provided, got {self.optimal_value}"
            )

        dist.setflags(write=False)
        dem.setflags(write=False)
        object.__setattr__(self, "distance_matrix", dist)
        object.__setattr__(self, "demands", dem)
        object.__setattr__(self, "capacity", cap)
        object.__setattr__(self, "depot", dep)
        object.__setattr__(self, "coords", coords_arr)
        object.__setattr__(self, "latlon", latlon_arr)

    @property
    def num_nodes(self) -> int:
        return int(self.demands.shape[0])

    @property
    def num_customers(self) -> int:
        return self.num_nodes - 1

    @property
    def customers(self) -> list[int]:
        return [i for i in range(self.num_nodes) if i != self.depot]

    @property
    def is_symmetric(self) -> bool:
        return bool(
            np.allclose(
                self.distance_matrix, self.distance_matrix.T, rtol=1e-9, atol=1e-12
            )
        )
