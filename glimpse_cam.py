#!/usr/bin/env python

import time, datetime, os, glob, socket, signal 
import RPi.GPIO as GPIO 
import subprocess as sub 
import sys 
import logging 
from gpiozero import Button

# Global variables
BUZZER_PIN = 5 
BATTERY_PIN = 4
BUTTON_PIN = 12 
LOGGER = None
RECORD_BUTTON = None
SHUTDOWN = False
CAMERA = None
BATTERY = None

def signal_handler(sig, frame):
    global SHUTDOWN
    SHUTDOWN = True # DO NOT REMOVE
    LOGGER.info("stopped by keyboard interrupt.")
    LOGGER.info("graceful exit.")
    GPIO.cleanup(BUZZER_PIN)

def buzzMotor(interval = 0.75):
	GPIO.output(BUZZER_PIN, GPIO.HIGH)
	time.sleep(interval)
	GPIO.output(BUZZER_PIN, GPIO.LOW)
	time.sleep(interval)
	GPIO.output(BUZZER_PIN, GPIO.HIGH)
	time.sleep(interval)
	GPIO.output(BUZZER_PIN, GPIO.LOW)


def buzzMotor2():    
        buzzMotor(0.25)
        time.sleep(0.2)
        buzzMotor(0.25)
        time.sleep(0.2)
        buzzMotor(0.25)

# Raises RuntimeError if fails to record
def record10(): 
    try:
        sub.check_call('echo "record on 10 10" > /home/pi/pikrellcam/www/FIFO', shell=True)
        LOGGER.info("pikrellcam record success.")
        # sleep only for 10 seconds since this is the time to record
	time.sleep(10)
    except sub.CalledProcessError:
        raise RuntimeError("pikrellcam record failure.")

def buttonPressResponse():
    try:
        buzzMotor(1.0)
        LOGGER.info("buzz motor success.")
    except:
        raise RuntimeError("buzz motor failure.")

# Raises RuntimeError
def checkCamera():
    global CAMERA
    try:
        if CAMERA:
            CAMERA.poll()
            if not CAMERA.returncode: 
                return True
            LOGGER.error("pikrellcam is no longer running.")
        else:
            LOGGER.error("pikrellcam check called with no camera started.")
        return False
    except Exception as e:
        LOGGER.error(str(e))
        raise RuntimeError("failed to check camera.");

def startCamera():
    global CAMERA
    try:
        CAMERA = sub.Popen(['/home/pi/pikrellcam/pikrellcam'])
        LOGGER.info("pikrellcam start success.")
    except OSError, ValueError:
        raise RuntimeError("pikrellcam start failed.")

def killCamera():
    global CAMERA
    try:
        if CAMERA:
            CAMERA.poll()
            if CAMERA.returncode:
                CAMERA.kill()
    except Exception as e:
        LOGGER.error(str(e))
        LOGGER.error("failed to kill camera.")


def runCamera():
    while not SHUTDOWN:
        # just keep the camera running for now 
        # and let the callbacks handle the rest
        try:
            if not checkCamera():
                startCamera()
        except RuntimeError as e:
            LOGGER.error(str(e))
    killCamera()

def triggerRecord():
    try:
        LOGGER.info("button pressed, starting record.")
        buttonPressResponse()
        record10()
        LOGGER.info("record finished.")
    except RuntimeError as e:
        LOGGER.error(str(e))

def lowBatteryLog():
    LOGGER.info("low battery.")

def setupCallbacks():
    try:
        RECORD_BUTTON.when_pressed = triggerRecord
        BATTERY.when_pressed = lowBatteryLog
        LOGGER.info("setup callbacks success.")
    except Exception as e:
        LOGGER.error(str(e))
        raise RuntimeError("setup callbacks failure.")

def setupLogger():
    # Sets up log, if this fails we're screwed.
    global LOGGER
    logFormat='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s'
    logging.basicConfig(
            filename="glimpse-log.log",
            level=logging.DEBUG,
            format=logFormat
    )
    LOGGER = logging.getLogger()

    # Add --console-log argument to add console logging
    if len(sys.argv) > 1 and sys.argv[1] == '--console-log':
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.setFormatter(logging.Formatter(logFormat))
        LOGGER.addHandler(stdout_handler)

if __name__=="__main__":
    # setup
    try: 
        # setup signal handler for kill signal
        signal.signal(signal.SIGINT, signal_handler)

        setupLogger()

        # setup the Buzzer
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUZZER_PIN, GPIO.OUT)

        # recognize Glimpse Cam Hardware
        RECORD_BUTTON = Button(BUTTON_PIN)
        # low battery warning sent when pin 4 pulled low
        # only read button click every 60s
        BATTERY = Button(BATTERY_PIN, pull_up=False, bounce_time=60)

        setupCallbacks()

        startCamera()

        # buzz motor for success
        buzzMotor2()

        LOGGER.info("setup success.")
    except Exception as e:
        LOGGER.error("setup failed.")
        LOGGER.error(str(e))
        print(sys.exc_info()[0])
        raise

    # run the camera
    runCamera()
