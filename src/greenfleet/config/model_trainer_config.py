from pathlib import Path


class ModelTrainerConfig:
    def __init__(
        self,
        transformed_train_file_path: Path,
        transformed_test_file_path: Path,
        model_dir: Path = Path("artifacts/model_trainer"),
    ):
        self.transformed_train_file_path = Path(
            transformed_train_file_path
        )

        self.transformed_test_file_path = Path(
            transformed_test_file_path
        )

        self.model_dir = Path(model_dir)

        self.model_dir.mkdir(
            parents=True,
            exist_ok=True,
        )