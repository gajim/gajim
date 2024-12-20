"""
This type stub file was generated by pyright.
"""

from typing import Optional
from typing import TypeVar
from typing import Union

import datetime

from winrt.windows.data.xml.dom import IXmlNode
from winrt.windows.data.xml.dom import XmlDocument
from winrt.windows.data.xml.dom import XmlElement

from .toast import Toast
from .toast_audio import ToastAudio
from .wrappers import ToastButton
from .wrappers import ToastDisplayImage
from .wrappers import ToastDuration
from .wrappers import ToastInputSelectionBox
from .wrappers import ToastInputTextBox
from .wrappers import ToastProgressBar
from .wrappers import ToastScenario
from .wrappers import ToastSystemButton

IXmlType = TypeVar("IXmlType", IXmlNode, XmlElement)

class ToastDocument:
    """
    The XmlDocument wrapper for toasts, which applies all the
    attributes configured in :class:`~windows_toasts.toast.Toast`
    """

    xmlDocument: XmlDocument
    bindingNode: IXmlType
    _inputFields: int
    def __init__(self, toast: Toast) -> None: ...
    @staticmethod
    def GetAttributeValue(nodeAttribute: IXmlType, attributeName: str) -> str:
        """
        Helper function that returns an attribute's value

        :param nodeAttribute: Node that has the attribute
        :type nodeAttribute: IXmlType
        :param attributeName: Name of the attribute, e.g. "duration"
        :type attributeName: str
        :return: The value of the attribute
        :rtype: str
        """
        ...

    def GetElementByTagName(self, tagName: str) -> Optional[IXmlType]:
        """
        Helper function to get the first element by its tag name

        :param tagName: The name of the tag for the element
        :type tagName: str
        :rtype: IXmlType
        """
        ...

    def SetAttribute(
        self, nodeAttribute: IXmlType, attributeName: str, attributeValue: str
    ) -> None:
        """
        Helper function to set an attribute to a node. <nodeAttribute attributeName="attributeValue" />

        :param nodeAttribute: Node to apply attributes to
        :type nodeAttribute: IXmlType
        :param attributeName: Name of the attribute, e.g. "duration"
        :type attributeName: str
        :param attributeValue: Value of the attribute, e.g. "long"
        :type attributeValue: str
        """
        ...

    def SetNodeStringValue(self, targetNode: IXmlType, newValue: str) -> None:
        """
        Helper function to set the inner value of a node. <text>newValue</text>

        :param targetNode: Node to apply attributes to
        :type targetNode: IXmlType
        :param newValue: Inner text of the node, e.g. "Hello, World!"
        :type newValue: str
        """
        ...

    def SetAttributionText(self, attributionText: str) -> None:
        """
        Set attribution text for the toast. This is used if we're using
        :class:`~windows_toasts.toasters.InteractableWindowsToaster` but haven't set up our own AUMID.
        `AttributionText on Microsoft.com <https://learn.microsoft.com/windows/apps/design/shell/tiles-and
        -notifications/adaptive-interactive-toasts#attribution-text>`_

        :param attributionText: Attribution text to set
        """
        ...

    def SetAudioAttributes(self, audioConfiguration: ToastAudio) -> None:
        """
        Apply audio attributes for the toast. If a loop is requested, the toast duration has to be set to long. `Audio
        on Microsoft.com <https://learn.microsoft.com/windows/apps/design/shell/tiles-and-notifications/adaptive
        -interactive-toasts#audio>`_
        """
        ...

    def SetTextField(self, nodePosition: int) -> None:
        """
        Set a simple text field. `Text elements on Microsoft.com
        <https://learn.microsoft.com/windows/apps/design/shell/tiles-and-notifications/adaptive-interactive-toasts#text-elements>`_

        :param nodePosition: Index of the text fields of the toast type for the text to be written in
        """
        ...

    def SetTextFieldStatic(self, nodePosition: int, newValue: str) -> None:
        """
        :meth:`SetTextField` but static, generally used for scheduled toasts

        :param nodePosition: Index of the text fields of the toast type for the text to be written in
        :param newValue: Content value of the text field
        """
        ...

    def SetCustomTimestamp(self, customTimestamp: datetime.datetime) -> None:
        """
        Apply a custom timestamp to display on the toast and in the notification center. `Custom timestamp on
        Microsoft.com <https://learn.microsoft.com/windows/apps/design/shell/tiles-and-notifications/adaptive
        -interactive-toasts?tabs=xml#custom-timestamp>`_

        :param customTimestamp: The target datetime
        :type customTimestamp: datetime.datetime
        """
        ...

    def AddImage(self, displayImage: ToastDisplayImage) -> None:
        """
        Add an image to display. `Inline image on Microsoft.com <https://learn.microsoft.com/windows/
        apps/design/shell/tiles-and-notifications/adaptive-interactive-toasts#inline-image>`_

        :type displayImage: ToastDisplayImage
        """
        ...

    def SetScenario(self, scenario: ToastScenario) -> None:
        """
        Set whether the notification should be marked as important. `Important Notifications on Microsoft.com
        <https://learn.microsoft.com/windows/apps/design/shell/tiles-and-notifications/adaptive-interactive-toasts
        #important-notifications>`_

        :param scenario: Scenario to mark the toast as
        :type scenario: ToastScenario
        """
        ...

    def AddInput(
        self, toastInput: Union[ToastInputTextBox, ToastInputSelectionBox]
    ) -> None:
        """
        Add a field for the user to input. `Inputs with button bar on Microsoft.com
        <https://learn.microsoft.com/windows/apps/design/shell/tiles-and-notifications/adaptive-interactive
        -toasts#quick-reply-text-box>`_

        :type toastInput: Union[ToastInputTextBox, ToastInputSelectionBox]
        """
        ...

    def SetDuration(self, duration: ToastDuration) -> None:
        """
        Set the duration of the toast. If looping audio is enabled, it will automatically be set to long

        :type duration: ToastDuration
        """
        ...

    def AddAction(self, action: Union[ToastButton, ToastSystemButton]) -> None:
        """
        Adds a button to the toast. Only works on :obj:`~windows_toasts.toasters.InteractableWindowsToaster`

        :type action: Union[ToastButton, ToastSystemButton]
        """
        ...

    def AddProgressBar(self) -> None:
        """
        Add a progress bar on your app notification to keep the user informed of the progress of operations.
        `Progress bar on Microsoft.com <https://learn.microsoft.com/windows/apps/design/shell/tiles-and-notifications
        /adaptive-interactive-toasts#progress-bar>`_
        """
        ...

    def AddStaticProgressBar(self, progressBar: ToastProgressBar) -> None:
        """
        :meth:`AddProgressBar` but static, generally used for scheduled toasts
        """
        ...
