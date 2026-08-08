from __future__ import annotations

import unittest

from src.models.common import fit_with_accelerator_fallback


class AcceleratorTests(unittest.TestCase):
    def test_auto_retries_on_cpu_when_gpu_fit_fails(self) -> None:
        fitted: list[str] = []

        def fit(model: str) -> None:
            if model == "gpu":
                raise RuntimeError("no GPU")
            fitted.append(model)

        model, device = fit_with_accelerator_fallback(
            "test",
            {"modeling": {"accelerator": "auto"}},
            lambda: "gpu",
            lambda: "cpu",
            fit,
        )

        self.assertEqual((model, device, fitted), ("cpu", "cpu", ["cpu"]))

    def test_gpu_mode_does_not_silently_fallback(self) -> None:
        with self.assertRaises(RuntimeError):
            fit_with_accelerator_fallback(
                "test",
                {"modeling": {"accelerator": "gpu"}},
                lambda: "gpu",
                lambda: "cpu",
                lambda _: (_ for _ in ()).throw(RuntimeError("no GPU")),
            )

