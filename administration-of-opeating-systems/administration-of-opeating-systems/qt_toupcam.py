import sys, toupcam, os
from time import sleep, time
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QLabel, QApplication, QWidget, QDesktopWidget, QCheckBox, QMessageBox
from dataclasses import dataclass
from scanner_camera import ScannerCamera
from structlog import get_logger

logger = get_logger()

class MainWin(QWidget):
    eventImage = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.cameras: list[ScannerCamera] = []
        self.hcam = None
        self.buf = None      # video buffer
        self.w = 0           # video width
        self.h = 0           # video height
        self.total = 0
        self.setFixedSize(800, 600)
        qtRectangle = self.frameGeometry()
        centerPoint = QDesktopWidget().availableGeometry().center()
        qtRectangle.moveCenter(centerPoint)
        self.move(qtRectangle.topLeft())
        # self.initUI()
        self.initCamera()

    def initUI(self):
        self.cb = QCheckBox('Auto Exposure', self)
        self.cb.stateChanged.connect(self.changeAutoExposure)
        self.label = QLabel(self)
        self.label.setScaledContents(True)
        self.label.move(0, 30)
        self.label.resize(self.geometry().width(), self.geometry().height())


# the vast majority of callbacks come from toupcam.dll/so/dylib internal threads, so we use qt signal to post this event to the UI thread
    @staticmethod
    def cameraCallback(nEvent, ctx):
        if nEvent == toupcam.TOUPCAM_EVENT_IMAGE:
            ctx.eventImage.emit()

# run in the UI thread
    @pyqtSlot()
    def eventImageSignal(self):
        images_path = os.path.join('.', 'images')
        if not os.path.exists(os.path.join(images_path)):
            os.mkdir(images_path)
        for camera in self.cameras:
            buffer = bytes(self.bufsize)
            try:
                camera.camera.PullImageV2(buffer, 24, None)
                self.total += 1
            except toupcam.HRESULTException as ex:
                QMessageBox.warning(self, '', 'pull image failed, hr=0x{:x}'.format(ex.hr), QMessageBox.Ok)
            else:
                image_path = os.path.join(images_path, camera.name) + '.png'
                # self.setWindowTitle('{}: {}'.format(self.camname, self.total))
                img = QImage(buffer, self.w, self.h, (self.w * 24 + 31) // 32 * 4, QImage.Format_RGB888)
                # self.label.setPixmap(QPixmap.fromImage(img))
                img.save(image_path, 'png')

    def initCamera(self):
        a: list[toupcam.ToupcamDeviceV2] = toupcam.Toupcam.EnumV2()
        if len(a) <= 0:
            # self.setWindowTitle('No camera found')
            print('')
            # self.cb.setEnabled(False)
        else:
            # self.camname = a[0].displayname
            # self.setWindowTitle(self.camname)
            self.eventImage.connect(self.eventImageSignal)
            for i in a:
                try:
                    camera = ScannerCamera(
                        toupcam.Toupcam.Open(i.id),
                        i.displayname,
                        i.id
                    )
                    active_camera = camera.camera
                except toupcam.HRESULTException as ex:
                    QMessageBox.warning(self, '', 'failed to open camera, hr=0x{:x}'.format(ex.hr), QMessageBox.Ok)
                else:
                    self.w, self.h = active_camera.get_Size()
                    bufsize = ((self.w * 24 + 31) // 32 * 4) * self.h
                    self.bufsize = bufsize
                    self.buf = bytes(bufsize)
                    # self.cb.setChecked(self.hcam.get_AutoExpoEnable())
                    try:
                        if sys.platform == 'win32':
                            active_camera.put_Option(toupcam.TOUPCAM_OPTION_BYTEORDER, 0) # QImage.Format_RGB888
                        active_camera.StartPullModeWithCallback(self.cameraCallback, self)
                    except toupcam.HRESULTException as ex:
                        QMessageBox.warning(self, '', 'failed to start camera, hr=0x{:x}'.format(ex.hr), QMessageBox.Ok)
                    self.cameras.append(camera)

    def changeAutoExposure(self, state):
        if self.hcam is not None:
            self.hcam.put_AutoExpoEnable(state == Qt.Checked)

    def closeEvent(self, _):
        if self.hcam is not None:
            self.hcam.Close()
            self.hcam = None

class Aos:
    def __init__(self, sleep_time=5):
        self.sleep_time = sleep_time
        self.scanner_cameras: list[ScannerCamera] = []
        self.frame_width = 0
        self.frame_height = 0
        self.buffer_size = 0
        self._init_cameras()

        while True:
#            self._snap_images()
#            sleep(self.sleep_time)
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
                # cam.camera.Trigger(1)
            except toupcam.HRESULTException as ex:
                logger.error(f"Can't get image from {cam.name}, error: 0x{ex.hr:x}")

    def _close(self):
        logger.info('closing cameras')
        for scanner_camera in self.scanner_cameras:
                scanner_camera.camera.Close()
    
    def _init_cameras(self):
        logger.info('start init cameras')
        toupcam_devices: list[toupcam.ToupcamDeviceV2] = toupcam.Toupcam.EnumV2()
        self.scanner_cameras = []
        if not toupcam_devices:
            logger.error("Can't find connected Toupcam devices")
            return
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
                # active_camera.StartPullModeWithCallback(self.camera_callback, self)
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
            # ctx.on_image_event()
    
    def on_image_event(self):
        self.get_image()
#        pass
    
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
