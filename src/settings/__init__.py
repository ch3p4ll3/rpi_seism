from pathlib import Path

import yaml
from pydantic import BaseModel

from .channel import Channel
from .spi import Spi


class Settings(BaseModel):
    network: str
    station: str

    sampling_rate: int
    spi: Spi
    channels: list[Channel]

    def export_settings(self):
        settings_file_path = Path(__file__).parent.parent.parent / "data/config.yml"

        with open(settings_file_path, "w", encoding="UTF-8") as settings_file:
            yaml.dump(self.model_dump(mode='json'), settings_file, indent=2)

    def update_from(self, new: "Settings") -> None:
        for field in Settings.model_fields:
            setattr(self, field, getattr(new, field))

    @classmethod
    def load_settings(cls):
        base_path = Path(__file__).parent.parent.parent / "data/config.yml"

        # If YAML config does not exist
        if not base_path.exists():
            if not base_path.parent.exists():
                base_path.parent.mkdir()
            # Otherwise create default config
            settings = cls.get_default_settings()

            with open(base_path, "w", encoding="UTF-8") as yml_file:
                yaml.dump(settings.model_dump(mode="json"), yml_file, indent=2)

            return settings

        # Load existing YAML config
        with open(base_path, "r", encoding="UTF-8") as yml_file:
            return cls(**yaml.safe_load(yml_file))

    @classmethod
    def get_default_settings(cls):
        data = {
            "network": "XX",
            "station": "RPI3",
            "sampling_rate": 100,
            "spi": {
                "rst_pin": 18,
                "cs_pin": 22,
                "cs_dac_pin": 23,
                "drdy_pin": 17
            },
            "channels": [
                {
                    "name": "EHZ",
                    "adc_channel": 0,
                    "orientation": "vertical",
                    "gain": 1000,
                    "sensitivity": 28.8,
                    "use_differential_channel": True
                },
                {
                    "name": "EHN",
                    "adc_channel": 1,
                    "orientation": "north",
                    "gain": 1000,
                    "sensitivity": 28.8,
                    "use_differential_channel": True
                },
                {
                    "name": "EHE",
                    "adc_channel": 2,
                    "orientation": "east",
                    "gain": 1000,
                    "sensitivity": 28.8,
                    "use_differential_channel": True
                }
            ]
        }

        return cls(**data)
