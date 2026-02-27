from pydantic import BaseModel, model_validator

from src.settings.enums import DataRate, PGA
from src.structs.mcu_settings import MCUSettingsFrame


# Map the Enum index to the actual frequency value (SPS)
SPS_MAPPING = {
    DataRate.DRATE_2SPS: 2.5,
    DataRate.DRATE_5SPS: 5,
    DataRate.DRATE_10SPS: 10,
    DataRate.DRATE_15SPS: 15,
    DataRate.DRATE_25SPS: 25,
    DataRate.DRATE_30SPS: 30,
    DataRate.DRATE_50SPS: 50,
    DataRate.DRATE_60SPS: 60,
    DataRate.DRATE_100SPS: 100,
    DataRate.DRATE_500SPS: 500,
    DataRate.DRATE_1000SPS: 1000,
    DataRate.DRATE_2000SPS: 2000,
    DataRate.DRATE_3750SPS: 3750,
    DataRate.DRATE_7500SPS: 7500,
    DataRate.DRATE_15000SPS: 15000,
    DataRate.DRATE_30000SPS: 30000,
}


class MCUSettings(BaseModel):
    sampling_rate: int

    adc_gain: PGA = PGA.PGA_64
    adc_sample_rate: DataRate = DataRate.DRATE_2000SPS

    @model_validator(mode='after')
    def validate_timing_margin(self) -> 'MCUSettings':
        actual_sps = SPS_MAPPING[self.adc_sample_rate]

        # Total time to cycle 3 channels (3 readings * 3 filter cycles each)
        # We add a 10% safety margin for SPI overhead
        estimated_conversion_time = (9.0 / actual_sps) * 1.10
        available_time = 1.0 / self.sampling_rate

        if estimated_conversion_time > available_time:
            # Find the best suggested DataRate based on the 13x Rule
            # (9x for physical settling + 4x for system headroom)
            min_required_sps = self.sampling_rate * 13
            suggestion = DataRate.DRATE_30000SPS # Default fallback

            # Sort mapping by SPS value and find the first one that satisfies the rule
            for rate, sps in sorted(SPS_MAPPING.items(), key=lambda x: x[1]):
                if sps >= min_required_sps:
                    suggestion = rate
                    break

            raise ValueError(
                f"Sampling Rate ({self.sampling_rate}Hz) is too high for the current ADC speed ({actual_sps} SPS)!\n"
                f"Multiplexing 3 channels requires ~{estimated_conversion_time*1000:.2f}ms, "
                f"but your loop only allows {available_time*1000:.2f}ms.\n\n"
                f"RECOMMENDATION: Increase 'adc_sample_rate' to "
                f"{SPS_MAPPING[suggestion]} SPS (Index: {suggestion}) to ensure the ADC can keep up."
            )
        return self

    @property
    def to_bytes(self) -> bytes:
        return MCUSettingsFrame(
            0xCC,
            0xDD,
            self.sampling_rate,
            self.adc_gain,
            self.adc_sample_rate
        ).to_bytes()
