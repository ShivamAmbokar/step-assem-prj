"""Thin OCP helpers (STEP I/O, volume, bounding box). This is where OCP imports start.

Only a handful of generic helpers live here; everything else (XCAF, B-rep queries, ...) is added
by the tasks that need it. Never import ``OCC.Core`` (pythonocc-core): one OCCT binding per
process.
"""
from __future__ import annotations

from pathlib import Path

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
from OCP.TopoDS import TopoDS_Shape


def read_step_shape(path: str | Path) -> TopoDS_Shape:
    """Read a STEP file into one shape (a compound when the file has several roots)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"STEP file not found: {path}")
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"OCCT could not read STEP file: {path}")
    if reader.TransferRoots() <= 0:
        raise RuntimeError(f"no transferable root entities in STEP file: {path}")
    return reader.OneShape()


def write_step_shape(shape: TopoDS_Shape, path: str | Path) -> Path:
    """Write ``shape`` to a STEP file (units: mm) and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = STEPControl_Writer()
    if writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone:
        raise RuntimeError("OCCT could not transfer the shape to a STEP model")
    if writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"OCCT could not write STEP file: {path}")
    return path


def volume(shape: TopoDS_Shape) -> float:
    """Volume of ``shape`` in mm^3 (OCCT global properties)."""
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def bbox(shape: TopoDS_Shape) -> tuple[float, float, float, float, float, float]:
    """Tight axis-aligned box ``(xmin, ymin, zmin, xmax, ymax, zmax)`` without tolerance gap."""
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    if box.IsVoid():
        raise ValueError("shape has an empty bounding box")
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return (float(xmin), float(ymin), float(zmin), float(xmax), float(ymax), float(zmax))
