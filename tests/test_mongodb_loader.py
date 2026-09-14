import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from greenfleet.database.mongodb import dataframe_to_documents, load_dataframe_to_mongodb


class MongoDBLoaderTests(unittest.TestCase):
    def test_dataframe_to_documents_converts_non_bson_values(self) -> None:
        frame = pd.DataFrame(
            {"index": [np.int64(1)], "fuel": [np.nan], "speed": [np.float64(12.5)]}
        )

        self.assertEqual(
            dataframe_to_documents(frame),
            [{"index": 1.0, "fuel": None, "speed": 12.5}],
        )

    @patch("greenfleet.database.mongodb.load_dotenv")
    @patch.dict("os.environ", {}, clear=True)
    def test_loader_requires_a_mongodb_uri(self, _load_dotenv) -> None:
        frame = pd.DataFrame({"record_id": ["one"], "fuel_consumption_rate": [2.0]})

        with self.assertRaisesRegex(ValueError, "MONGODB_URI"):
            load_dataframe_to_mongodb(frame)

    def test_loader_requires_a_unique_key(self) -> None:
        frame = pd.DataFrame({"record_id": ["one", "one"], "fuel_consumption_rate": [2.0, 3.0]})

        with self.assertRaisesRegex(ValueError, "non-null and unique"):
            load_dataframe_to_mongodb(frame, uri="mongodb://unused")


if __name__ == "__main__":
    unittest.main()
