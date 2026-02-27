import numpy as np
from collections import deque


class STALTAProperty:
    """
    A simple implementation of the STA/LTA algorithm for earthquake detection.
    This class maintains two buffers for the short-term average (STA)
    and long-term average (LTA) of the signal energy, and provides a method to process
    incoming samples and determine if a trigger condition is met based on predefined thresholds.
    """
    def __init__(self, sta_sec=1.0, lta_sec=30.0, sampling_rate=100.0):
        self.sta_len = int(sta_sec * sampling_rate)
        self.lta_len = int(lta_sec * sampling_rate)

        # Buffers for squared values (energy)
        self.sta_buffer = deque(maxlen=self.sta_len)
        self.lta_buffer = deque(maxlen=self.lta_len)

        self.is_triggered = False
        self.on_threshold = 3.5  # Typical trigger value
        self.off_threshold = 1.5 # De-trigger when signal settles

    def process_sample(self, value):
        # We use squared values to calculate energy (rectification)
        energy = value**2
        self.sta_buffer.append(energy)
        self.lta_buffer.append(energy)

        if len(self.lta_buffer) < self.lta_len:
            return 1.0, False # Not enough data yet

        sta_mean = np.mean(self.sta_buffer)
        lta_mean = np.mean(self.lta_buffer)

        # Avoid division by zero
        ratio = sta_mean / lta_mean if lta_mean > 0 else 1.0

        # Hysteresis Logic
        if not self.is_triggered and ratio > self.on_threshold:
            self.is_triggered = True
        elif self.is_triggered and ratio < self.off_threshold:
            self.is_triggered = False

        return ratio, self.is_triggered
