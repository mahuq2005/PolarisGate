"""Data Classification labels for data flows."""
from enum import Enum

class DataLabel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"  
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"