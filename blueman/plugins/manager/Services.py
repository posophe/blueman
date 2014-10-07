from blueman.bluez.BlueZInterface import BlueZInterface
from blueman.bluez.Network import Network
from blueman.plugins.ManagerPlugin import ManagerPlugin
from gi.repository import Gtk

from blueman.Sdp import *
from blueman.Functions import *
from blueman.main.SignalTracker import SignalTracker
from blueman.gui.manager.ManagerProgressbar import ManagerProgressbar
from blueman.main.Config import Config
from blueman.main.AppletService import AppletService
from blueman.gui.MessageArea import MessageArea
from blueman.services import *

from blueman.Lib import rfcomm_list


def get_x_icon(icon_name, size):
    ic = get_icon(icon_name, size)
    x = get_icon("blueman-x", size)
    pixbuf = composite_icon(ic, [(x, 0, 0, 255)])

    return pixbuf


class Services(ManagerPlugin):
    connectable_uuids = [HID_SVCLASS_ID, AUDIO_SOURCE_SVCLASS_ID, AUDIO_SINK_SVCLASS_ID, HEADSET_SVCLASS_ID, HANDSFREE_SVCLASS_ID]

    def on_request_menu_items(self, manager_menu, device):
        items = []
        appl = AppletService()

        for service in device.get_services():
            if service.group == 'network':
                manager_menu.Signals.Handle("bluez", Network(device.get_object_path()),
                                            manager_menu.service_property_changed, "PropertyChanged")

            if isinstance(service, Input):
                manager_menu.Signals.Handle("bluez", device, manager_menu.service_property_changed, "PropertyChanged")

            if service.connected:
                item = create_menuitem(service.name, get_x_icon(service.icon, 16))
                manager_menu.Signals.Handle("gobject", item, "activate", manager_menu.on_disconnect, service)
                items.append((item, service.priority + 100))
            else:
                item = create_menuitem(service.name, get_icon(service.icon, 16))
                if service.description:
                    item.props.tooltip_text = service.description
                manager_menu.Signals.Handle("gobject", item, "activate", manager_menu.on_connect, service)
                items.append((item, service.priority))
            item.show()

            if service.group == 'network' and service.connected:
                if "DhcpClient" in appl.QueryPlugins():
                    def renew(x):
                        appl.DhcpClient(Network(device.get_object_path()).get_properties()["Interface"])

                    item = create_menuitem(_("Renew IP Address"), get_icon("gtk-refresh", 16))
                    manager_menu.Signals.Handle("gobject", item, "activate", renew)
                    item.show()
                    items.append((item, 201))

        return items

    # TODO: Serial support
    def dead_serial_code(self, manager_menu, device):
        items = []
        uuids = device.UUIDs
        appl = AppletService()

        for name, service in device.Services.items():
            if name == "serial":
                ports_list = rfcomm_list()

                def flt(dev):
                    if dev["dst"] == device.Address and dev["state"] == "connected":
                        return dev["channel"]

                active_ports = map(flt, ports_list)


                def get_port_id(channel):
                    for dev in ports_list:
                        if dev["dst"] == device.Address and dev["state"] == "connected" and dev["channel"] == channel:
                            return dev["id"]

                serial_items = []

                has_dun = False
                try:
                    for port_name, channel, uuid in sdp_get_cached_rfcomm(device.Address):

                        if SERIAL_PORT_SVCLASS_ID in uuid:
                            if name is not None:
                                if channel in active_ports:
                                    item = create_menuitem(port_name, get_x_icon("blueman-serial", 16))
                                    manager_menu.Signals.Handle("gobject", item, "activate", manager_menu.on_disconnect, service, "/dev/rfcomm%d" % get_port_id(channel))
                                    item.show()
                                    items.append((item, 150))
                                else:
                                    item = create_menuitem(port_name, get_icon("blueman-serial", 16))
                                    manager_menu.Signals.Handle("gobject", item, "activate", manager_menu.on_connect, service)
                                    item.show()
                                    serial_items.append(item)


                        elif DIALUP_NET_SVCLASS_ID in uuid:
                            if name is not None:
                                if channel in active_ports:
                                    item = create_menuitem(port_name, get_x_icon("modem", 16))
                                    manager_menu.Signals.Handle("gobject", item, "activate", manager_menu.on_disconnect, service, "/dev/rfcomm%d" % get_port_id(channel))
                                    item.show()
                                    items.append((item, 150))
                                else:
                                    item = create_menuitem(port_name, get_icon("modem", 16))
                                    manager_menu.Signals.Handle("gobject", item, "activate", manager_menu.on_connect, service)
                                    item.show()
                                    serial_items.append(item)
                                    has_dun = True

                except KeyError:
                    for uuid in uuids:
                        uuid16 = uuid128_to_uuid16(uuid)
                        if uuid16 == DIALUP_NET_SVCLASS_ID:
                            item = create_menuitem(_("Dialup Service"), get_icon("modem", 16))
                            manager_menu.Signals.Handle("gobject", item, "activate", manager_menu.on_connect, service)
                            item.show()
                            serial_items.append(item)
                            has_dun = True

                        if uuid16 == SERIAL_PORT_SVCLASS_ID:
                            item = create_menuitem(_("Serial Service"), get_icon("blueman-serial", 16))
                            manager_menu.Signals.Handle("gobject", item, "activate", manager_menu.on_connect, service)
                            item.show()
                            serial_items.append(item)

                    for dev in ports_list:
                        if dev["dst"] == device.Address:
                            if dev["state"] == "connected":
                                devname = _("Serial Port %s") % "rfcomm%d" % dev["id"]

                                item = create_menuitem(devname, get_x_icon("modem", 16))
                                manager_menu.Signals.Handle("gobject", item, "activate", manager_menu.on_disconnect, service, "/dev/rfcomm%d" % dev["id"])
                                items.append((item, 120))
                                item.show()

                def open_settings(i, device):
                    from blueman.gui.GsmSettings import GsmSettings

                    d = GsmSettings(device.Address)
                    d.run()
                    d.destroy()

                if has_dun and "PPPSupport" in appl.QueryPlugins():
                    item = Gtk.SeparatorMenuItem()
                    item.show()
                    serial_items.append(item)

                    item = create_menuitem(_("Dialup Settings"),
                                           get_icon("gtk-preferences", 16))
                    serial_items.append(item)
                    item.show()
                    manager_menu.Signals.Handle("gobject", item,
                                                "activate", open_settings,
                                                device)

                if len(serial_items) > 1:
                    sub = Gtk.Menu()
                    sub.show()

                    item = create_menuitem(_("Serial Ports"), get_icon("modem", 16))
                    item.set_submenu(sub)
                    item.show()
                    items.append((item, 90))

                    for item in serial_items:
                        sub.append(item)

                else:
                    for item in serial_items:
                        items.append((item, 80))

        return items

