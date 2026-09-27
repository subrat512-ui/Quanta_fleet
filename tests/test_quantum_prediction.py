import json
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from greenfleet.ml_pipeline.quantum.qpso_svr import QPSOConfig
from greenfleet.ml_pipeline.quantum.training import train_quantum_svr


class QuantumPredictionTests(unittest.TestCase):
    def test_qpso_trainer_writes_reusable_pipeline(self):
        rng = np.random.default_rng(7)
        rows = 72
        speed = rng.uniform(8.0, 18.0, rows)
        load = rng.uniform(0.35, 1.0, rows)
        wind = rng.uniform(0.0, 18.0, rows)
        vessel_type = rng.choice(["bulk_carrier", "tanker"], rows)
        fuel = (
            3.0
            + 0.008 * speed**3
            + 2.0 * load
            + 0.04 * wind
            + (vessel_type == "tanker") * 1.2
            + rng.normal(0.0, 0.15, rows)
        )
        data = pd.DataFrame(
            {
                "speed": speed,
                "load": load,
                "wind": wind,
                "vessel_type": vessel_type,
                "fuel": fuel,
            }
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "training.csv"
            data.to_csv(csv_path, index=False)
            result = train_quantum_svr(
                csv_path,
                root / "output",
                numerical_features=["speed", "load", "wind"],
                categorical_features=["vessel_type"],
                target_column="fuel",
                qpso_config=QPSOConfig(population_size=4, iterations=2, random_state=3),
            )

            self.assertTrue(result.model_path.exists())
            report = json.loads(result.metrics_path.read_text(encoding="utf-8"))
            self.assertEqual(report["model"], "QPSO-tuned RBF SVR")
            self.assertEqual(report["evaluations"], 12)
            model = joblib.load(result.model_path)
            predictions = model.predict(data.iloc[:3])
            self.assertEqual(predictions.shape, (3,))
            self.assertTrue(np.isfinite(predictions).all())


if __name__ == "__main__":
    unittest.main()
