from dataclasses import dataclass
import toupcam

@dataclass
class ScannerCamera:
    camera: toupcam.Toupcam
    name: str
    id: str