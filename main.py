import sys, toupcam, os
from time import sleep
from PyQt5.QtGui import QImage
from scanner_camera import ScannerCamera
from structlog import get_logger

logger = get_logger()


class Aos:
    def __init__(self, sleep_time=5):
        self.sleep_time = sleep_time
        self.scanner_cameras: list[ScannerCamera] = []
        self.frame_width = 0
        self.frame_height = 0
        self.buffer_size = 0
        self._init_cameras()

        while True:
            try:
                self._snap_images()
                sleep(self.sleep_time)
                
            except KeyboardInterrupt:
                self._close()
                break
    
    def _snap_images(self):
        for cam in self.scanner_cameras:
            try:
                cam.camera.Snap(0)
            except toupcam.HRESULTException as ex:
                logger.error(f"Can't get image from {cam.name}, error: 0x{ex.hr:x}")

    def _close(self):
        logger.info('closing cameras')
        for scanner_camera in self.scanner_cameras:
                scanner_camera.camera.Close()
    
    def _init_cameras(self):
        logger.info('start init cameras')
        toupcam_devices: list[toupcam.ToupcamDeviceV2] = toupcam.Toupcam.EnumV2()
        while not toupcam_devices:
            logger.error("Can't find connected Toupcam devices")
            logger.error(f"Next check after {self.sleep_time} seconds")
            sleep(self.sleep_time)
        
        self.scanner_cameras = []
        for i, toupcam_device in enumerate(toupcam_devices):
            try:
                scanner_camera = ScannerCamera(
                    camera=toupcam.Toupcam.Open(toupcam_device.id),
                    name=toupcam_device.displayname + '_' + str(i+1),
                    id=toupcam_device.id
                )
                active_camera = scanner_camera.camera
            except toupcam.HRESULTException as ex:
                logger.error(f"Can't open camera, error: 0x{ex.hr:x}")
                raise
            self.frame_width, self.frame_height = active_camera.get_Size()
            self.bufsize = ((self.frame_width * 24 + 31) // 32 * 4) * self.frame_height
            try:
                active_camera.put_Option(toupcam.TOUPCAM_OPTION_TRIGGER, 0)
                active_camera.put_eSize(0)
            except toupcam.HRESULTException as ex:
               logger.error(f"Can't start camera, error: 0x{ex.hr:x}")
            self.scanner_cameras.append(scanner_camera)
        logger.info('cameras initialized')

    @staticmethod
    def camera_callback(event, ctx):
        if event == toupcam.TOUPCAM_EVENT_IMAGE:
            logger.debug('EVENT_IMAGE')
            ctx.on_image_event()
        elif event == toupcam.TOUPCAM_EVENT_STILLIMAGE:
            logger.debug('still image')
    
    def on_image_event(self):
        self.get_image()
    
    def get_image(self):
        images_path = os.path.join('.', 'images')
        if not os.path.exists(os.path.join(images_path)):
            os.mkdir(images_path)
        for camera in self.scanner_cameras:
            buffer = bytes(self.bufsize)
            logger.info(f'getting image from {camera.name}')
            try:
                camera.camera.PullImageV2(buffer, 24, None)
            except toupcam.HRESULTException as ex:
                logger.debug(f'pull image from {camera.name} failed, hr=0x{ex.hr}')
            else:
                image_path = os.path.join(images_path, camera.name) + '.png'
                img = QImage(buffer, self.frame_width, self.frame_height, (self.frame_width * 24 + 31) // 32 * 4, QImage.Format_RGB888)
                img.save(image_path, 'png')


if __name__ == '__main__':
    aos = Aos(5)
