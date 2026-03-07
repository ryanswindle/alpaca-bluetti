from typing import Annotated, Dict

from fastapi import APIRouter, Depends, Form, HTTPException, Query

from exceptions import (
    DriverException,
    InvalidOperationException,
    InvalidValueException,
    NotConnectedException,
    NotImplementedException,
)
from log import get_logger
from responses import MethodResponse, PropertyResponse, StateValue
from shr import AlpacaGetParams, AlpacaPutParams, to_bool
from switch_device import SwitchDevice


logger = get_logger()

router = APIRouter(prefix="/api/v1/switch", tags=["Switch"])

devices: Dict[int, SwitchDevice] = {}


def set_devices(dev_dict: Dict[int, SwitchDevice]):
    global devices
    devices = dev_dict


def get_device(devnum: int) -> SwitchDevice:
    if devnum not in devices:
        raise HTTPException(
            status_code=400,
            detail=f"Device number {devnum} does not exist.",
        )
    return devices[devnum]


##################################
# High-level device/library info #
##################################
class DeviceMetadata:
    Name = "Bluetti"
    Version = "1.0.0"
    Description = "Bluetti Solar Generator ASCOM Alpaca Driver"
    DeviceType = "Switch"
    Info = "Alpaca Device\nImplements ISwitchV3\nASCOM Initiative"
    InterfaceVersion = 3


def _connected_property(device: SwitchDevice, value, params):
    """Helper for simple properties that require connection."""
    if not device.connected:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    return PropertyResponse.create(
        value=value,
        client_transaction_id=params.client_transaction_id,
    ).model_dump()


def _validate_switch_id(device: SwitchDevice, switch_id: int):
    """Return an InvalidValueException if switch_id is out of range, else None."""
    if switch_id < 0 or switch_id >= device.max_switch:
        return InvalidValueException(
            f"Id {switch_id} is out of range (0 to {device.max_switch - 1})."
        )
    return None


#######################################
# ASCOM Methods Common To All Devices #
#######################################
@router.put("/{devnum}/action", summary="")
async def action(devnum: int, params: AlpacaPutParams = Depends()):
    return MethodResponse.create(
        client_transaction_id=params.client_transaction_id,
        error=NotImplementedException("Action"),
    ).model_dump()


@router.put("/{devnum}/commandblind", summary="")
async def commandblind(devnum: int, params: AlpacaPutParams = Depends()):
    return MethodResponse.create(
        client_transaction_id=params.client_transaction_id,
        error=NotImplementedException("CommandBlind"),
    ).model_dump()


@router.put("/{devnum}/commandbool", summary="")
async def commandbool(devnum: int, params: AlpacaPutParams = Depends()):
    return MethodResponse.create(
        client_transaction_id=params.client_transaction_id,
        error=NotImplementedException("CommandBool"),
    ).model_dump()


@router.put("/{devnum}/commandstring", summary="")
async def commandstring(devnum: int, params: AlpacaPutParams = Depends()):
    return MethodResponse.create(
        client_transaction_id=params.client_transaction_id,
        error=NotImplementedException("CommandString"),
    ).model_dump()


@router.put("/{devnum}/connect", summary="")
async def connect(devnum: int, params: AlpacaPutParams = Depends()):
    device = get_device(devnum)
    try:
        device.connect()
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.Connect failed", ex),
        ).model_dump()


@router.get("/{devnum}/connected", summary="")
async def connected_get(devnum: int, params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    return PropertyResponse.create(
        value=device.connected,
        client_transaction_id=params.client_transaction_id,
    ).model_dump()


@router.put("/{devnum}/connected", summary="")
async def connected_put(devnum: int, Connected: Annotated[str, Form()], params: AlpacaPutParams = Depends()):
    device = get_device(devnum)
    conn = to_bool(Connected)
    try:
        device.connected = conn
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except HTTPException:
        raise
    except Exception as ex:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.Connected failed", ex),
        ).model_dump()


@router.get("/{devnum}/connecting", summary="")
async def connecting_get(devnum: int, params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    return PropertyResponse.create(
        value=device.connecting,
        client_transaction_id=params.client_transaction_id,
    ).model_dump()


@router.get("/{devnum}/description", summary="")
async def description(devnum: int, params: AlpacaGetParams = Depends()):
    return PropertyResponse.create(
        value=DeviceMetadata.Description,
        client_transaction_id=params.client_transaction_id,
    ).model_dump()


@router.get("/{devnum}/devicestate", summary="")
async def devicestate(devnum: int, params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    try:
        val = []
        for i in range(device.max_switch):
            val.append(StateValue(Name=f"GetSwitch{i}", Value=device.get_switch(i)).model_dump())
            val.append(StateValue(Name=f"GetSwitchValue{i}", Value=device.get_switch_value(i)).model_dump())
        val.append(StateValue(Name="TimeStamp", Value=device.timestamp).model_dump())
        return PropertyResponse.create(
            value=val,
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.DeviceState failed", ex),
        ).model_dump()


@router.put("/{devnum}/disconnect", summary="")
async def disconnect(devnum: int, params: AlpacaPutParams = Depends()):
    device = get_device(devnum)
    try:
        device.disconnect()
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.Disconnect failed", ex),
        ).model_dump()


@router.get("/{devnum}/driverinfo", summary="")
async def driverinfo(devnum: int, params: AlpacaGetParams = Depends()):
    return PropertyResponse.create(
        value=DeviceMetadata.Info,
        client_transaction_id=params.client_transaction_id,
    ).model_dump()


@router.get("/{devnum}/driverversion", summary="")
async def driverversion(devnum: int, params: AlpacaGetParams = Depends()):
    return PropertyResponse.create(
        value=DeviceMetadata.Version,
        client_transaction_id=params.client_transaction_id,
    ).model_dump()


@router.get("/{devnum}/interfaceversion", summary="")
async def interfaceversion(devnum: int, params: AlpacaGetParams = Depends()):
    return PropertyResponse.create(
        value=DeviceMetadata.InterfaceVersion,
        client_transaction_id=params.client_transaction_id,
    ).model_dump()


@router.get("/{devnum}/name", summary="")
async def name(devnum: int, params: AlpacaGetParams = Depends()):
    return PropertyResponse.create(
        value=DeviceMetadata.Name,
        client_transaction_id=params.client_transaction_id,
    ).model_dump()


@router.get("/{devnum}/supportedactions", summary="")
async def supportedactions(devnum: int, params: AlpacaGetParams = Depends()):
    return PropertyResponse.create(
        value=[],
        client_transaction_id=params.client_transaction_id,
    ).model_dump()


########################
# ISwitchV3 properties #
########################
@router.get("/{devnum}/maxswitch", summary="")
async def maxswitch(devnum: int, params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    return _connected_property(device, device.max_switch, params)


#####################
# ISwitchV3 methods #
#####################
@router.get("/{devnum}/canasync", summary="")
async def canasync(devnum: int, Id: int = Query(...), params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    try:
        return PropertyResponse.create(
            value=device.can_async(Id),
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.CanAsync failed", ex),
        ).model_dump()


@router.put("/{devnum}/cancelasync", summary="")
async def cancelasync(devnum: int, Id: Annotated[int, Form()], params: AlpacaPutParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    try:
        device.cancel_async(Id)
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.CancelAsync failed", ex),
        ).model_dump()


@router.get("/{devnum}/canwrite", summary="")
async def canwrite(devnum: int, Id: int = Query(...), params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    try:
        return PropertyResponse.create(
            value=device.can_write(Id),
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.CanWrite failed", ex),
        ).model_dump()


@router.get("/{devnum}/getswitch", summary="")
async def getswitch(devnum: int, Id: int = Query(...), params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    try:
        return PropertyResponse.create(
            value=device.get_switch(Id),
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.GetSwitch failed", ex),
        ).model_dump()


@router.get("/{devnum}/getswitchdescription", summary="")
async def getswitchdescription(devnum: int, Id: int = Query(...), params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    try:
        return PropertyResponse.create(
            value=device.get_switch_description(Id),
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.GetSwitchDescription failed", ex),
        ).model_dump()


@router.get("/{devnum}/getswitchname", summary="")
async def getswitchname(devnum: int, Id: int = Query(...), params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    try:
        return PropertyResponse.create(
            value=device.get_switch_name(Id),
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.GetSwitchName failed", ex),
        ).model_dump()


@router.get("/{devnum}/getswitchvalue", summary="")
async def getswitchvalue(devnum: int, Id: int = Query(...), params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    try:
        return PropertyResponse.create(
            value=device.get_switch_value(Id),
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.GetSwitchValue failed", ex),
        ).model_dump()


@router.get("/{devnum}/maxswitchvalue", summary="")
async def maxswitchvalue(devnum: int, Id: int = Query(...), params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    try:
        return PropertyResponse.create(
            value=device.max_switch_value(Id),
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.MaxSwitchValue failed", ex),
        ).model_dump()


@router.get("/{devnum}/minswitchvalue", summary="")
async def minswitchvalue(devnum: int, Id: int = Query(...), params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    try:
        return PropertyResponse.create(
            value=device.min_switch_value(Id),
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.MinSwitchValue failed", ex),
        ).model_dump()


@router.put("/{devnum}/setasync", summary="")
async def setasync(devnum: int, Id: Annotated[int, Form()], State: Annotated[str, Form()], params: AlpacaPutParams = Depends()):
    return MethodResponse.create(
        client_transaction_id=params.client_transaction_id,
        error=NotImplementedException("SetAsync"),
    ).model_dump()


@router.put("/{devnum}/setasyncvalue", summary="")
async def setasyncvalue(devnum: int, Id: Annotated[int, Form()], Value: Annotated[float, Form()], params: AlpacaPutParams = Depends()):
    return MethodResponse.create(
        client_transaction_id=params.client_transaction_id,
        error=NotImplementedException("SetAsyncValue"),
    ).model_dump()


@router.put("/{devnum}/setswitch", summary="")
async def setswitch(devnum: int, Id: Annotated[int, Form()], State: Annotated[str, Form()], params: AlpacaPutParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    if not device.can_write(Id):
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=InvalidOperationException(f"Switch {Id} is read-only."),
        ).model_dump()
    state = to_bool(State)
    try:
        device.set_switch(Id, state)
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.SetSwitch failed", ex),
        ).model_dump()


@router.put("/{devnum}/setswitchname", summary="")
async def setswitchname(devnum: int, params: AlpacaPutParams = Depends()):
    return MethodResponse.create(
        client_transaction_id=params.client_transaction_id,
        error=NotImplementedException("SetSwitchName"),
    ).model_dump()


@router.put("/{devnum}/setswitchvalue", summary="")
async def setswitchvalue(devnum: int, Id: Annotated[int, Form()], Value: Annotated[float, Form()], params: AlpacaPutParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    if not device.can_write(Id):
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=InvalidOperationException(f"Switch {Id} is read-only."),
        ).model_dump()
    try:
        device.set_switch_value(Id, Value)
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return MethodResponse.create(
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.SetSwitchValue failed", ex),
        ).model_dump()


@router.get("/{devnum}/statechangecomplete", summary="")
async def statechangecomplete(devnum: int, Id: int = Query(...), params: AlpacaGetParams = Depends()):
    return MethodResponse.create(
        client_transaction_id=params.client_transaction_id,
        error=NotImplementedException("StateChangeComplete"),
    ).model_dump()


@router.get("/{devnum}/switchstep", summary="")
async def switchstep(devnum: int, Id: int = Query(...), params: AlpacaGetParams = Depends()):
    device = get_device(devnum)
    if not device.connected:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=NotConnectedException(),
        ).model_dump()
    err = _validate_switch_id(device, Id)
    if err:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=err,
        ).model_dump()
    try:
        return PropertyResponse.create(
            value=device.switch_step(Id),
            client_transaction_id=params.client_transaction_id,
        ).model_dump()
    except Exception as ex:
        return PropertyResponse.create(
            value=None,
            client_transaction_id=params.client_transaction_id,
            error=DriverException(0x500, "Switch.SwitchStep failed", ex),
        ).model_dump()
