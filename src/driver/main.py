#!/usr/bin/python
# -*- coding:utf-8 -*-
from src.driver.ads1256 import ADS1256
from src.driver.enums import ScanMode
from src.settings import Settings


try:
    ADC = ADS1256(Settings.load_settings())
    ADC.ADS1256_init()
    ADC.set_mode(ScanMode.DIFFERENTIAL_INPUT)

    while(1):
        ADC_Value = ADC.get_all_channels()
        print ("0 ADC = %lf"%(ADC_Value[0]*5.0/0x7fffff))
        print ("1 ADC = %lf"%(ADC_Value[1]*5.0/0x7fffff))
        print ("\33[9A")

except Exception as e:
    print(e)
    #GPIO.cleanup()
    print ("\r\nProgram end     ")

    exit()
