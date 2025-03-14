"""
This type stub file was generated by pyright.
"""

from typing import Optional
from typing import Sequence
from typing import Union

import abc
from dataclasses import dataclass
from enum import Enum
from os import PathLike

class ToastButtonColour(Enum):
    """
    Possible colours for toast buttons
    """

    Default = ...
    Green = ...
    Red = ...

class ToastDuration(Enum):
    """
    Possible values for duration to display toast for
    """

    Default: str = ...
    Short: str = ...
    Long: str = ...

class ToastImagePosition(Enum):
    """
    Allowed positions for an image to be placed on a toast notification
    """

    Inline = ...
    Hero = ...
    AppLogo = ...

class ToastScenario(Enum):
    """
    Possible scenarios for the toast
    """

    Default: str = ...
    Alarm: str = ...
    Reminder: str = ...
    IncomingCall: str = ...
    Important: str = ...

class ToastSystemButtonAction(Enum):
    Snooze = ...
    Dismiss = ...

@dataclass(init=False)
class ToastImage:
    """
    Image that can be displayed in various toast elements
    """

    path: str
    def __init__(self, imagePath: Union[str, PathLike]) -> None:
        """
        Initialise an :class:`ToastImage` class to use in certain classes.
        Online images are supported only in packaged apps that have the internet capability in their manifest.
        Unpackaged apps don't support http images; you must download the image to your local app data,
        and reference it locally.

        :param imagePath: The path to an image file
        :type imagePath: Union[str, PathLike]
        :raises: InvalidImageException: If the path to an online image is supplied
        """
        ...

@dataclass
class ToastDisplayImage:
    """
    Define an image that will be displayed as the icon of the toast
    """

    image: ToastImage
    altText: Optional[str] = ...
    position: ToastImagePosition = ...
    circleCrop: bool = ...
    @classmethod
    def fromPath(
        cls,
        imagePath: Union[str, PathLike],
        altText: Optional[str] = ...,
        position: ToastImagePosition = ...,
        circleCrop: bool = ...,
    ) -> ToastDisplayImage:
        """
        Create a :class:`ToastDisplayImage` object from path without having to create :class:`ToastImage`
        """
        ...

@dataclass
class ToastProgressBar:
    """
    Progress bar to be included in a toast
    """

    status: str
    caption: Optional[str] = ...
    progress: Optional[float] = ...
    progress_override: Optional[str] = ...

@dataclass
class _ToastInput(abc.ABC):
    """
    Base input dataclass to be used in toasts
    """

    input_id: str
    caption: str = ...

@dataclass(init=False)
class ToastInputTextBox(_ToastInput):
    """
    A text box that can be added in toasts for the user to enter their input
    """

    placeholder: str = ...
    def __init__(
        self, input_id: str, caption: str = ..., placeholder: str = ...
    ) -> None: ...

@dataclass
class ToastSelection:
    """
    An item that the user can select from the drop down list
    """

    selection_id: str
    content: str
    ...

@dataclass(init=False)
class ToastInputSelectionBox(_ToastInput):
    """
    A selection box control, which lets users pick from a dropdown list of options
    """

    selections: Sequence[ToastSelection] = ...
    default_selection: Optional[ToastSelection] = ...
    def __init__(
        self,
        input_id: str,
        caption: str = ...,
        selections: Sequence[ToastSelection] = ...,
        default_selection: Optional[ToastSelection] = ...,
    ) -> None: ...

@dataclass
class ToastButton:
    """
    A button that the user can click on a toast notification
    """

    content: str = ...
    arguments: str = ...
    image: Optional[ToastImage] = ...
    relatedInput: Optional[Union[ToastInputTextBox, ToastInputSelectionBox]] = ...
    inContextMenu: bool = ...
    tooltip: Optional[str] = ...
    launch: Optional[str] = ...
    colour: ToastButtonColour = ...

@dataclass
class ToastSystemButton:
    """
    Button used to perform a system action, snooze or dismiss
    """

    action: ToastSystemButtonAction
    content: str = ...
    relatedInput: Optional[ToastInputSelectionBox] = ...
    image: Optional[ToastImage] = ...
    tooltip: Optional[str] = ...
    colour: ToastButtonColour = ...
