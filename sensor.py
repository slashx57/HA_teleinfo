#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import time
import optparse
import logging
from datetime import timedelta
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
  CONF_NAME, CONF_RESOURCES, STATE_UNKNOWN, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pyftdi>=0.29.3']
from pyftdi.ftdi import Ftdi
import pyftdi.serialext
from serial import PARITY_EVEN, SEVENBITS, EIGHTBITS, STOPBITS_ONE

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'teleinfo'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

# Misc
STX = '\x02'  # start of text
ETX = '\x03'  # end of text
EOT = '\x04'  # end of transmission

SENSOR_TYPES = {
  'adco': ['Contrat', '', 'mdi:numeric'],         # N° d’identification du compteur : ADCO(12 caractères)
  'optarif': ['Option tarifaire', '', 'mdi:file-document-edit'],    # Option tarifaire(type d’abonnement) : OPTARIF(4 car.)
  'isousc': ['Intensité souscrite', 'A', 'mdi:information-outline'],    # Intensité souscrite : ISOUSC( 2 car.unité = ampères)
  'hchc': ['Heures creuses', 'Wh', 'mdi:timelapse'],      # Index heures creuses si option = heures creuses : HCHC( 9 car.unité = Wh)
  'hchp': ['Heures pleines', 'Wh', 'mdi:timelapse'],      # Index heures pleines si option = heures creuses : HCHP( 9 car.unité = Wh)
  'ptec': ['Période Tarifaire', '', 'mdi:clock-outline'],     # Période tarifaire en cours : PTEC( 4 car.)
  'iinst': ['Intensite instantanee', 'A', 'mdi:current-ac'],    # Intensité instantanée : IINST( 3 car.unité = ampères)
  'imax': ['Intensite max', 'A', 'mdi:format-vertical-align-top'],  # Intensité maximale : IMAX( 3 car.unité = ampères)
  'papp': ['Puissance apparente', 'VA', 'mdi:flash'],     # Puissance apparente : PAPP( 5 car.unité = Volt.ampères)
  'hhphc': ['Groupe horaire', '', 'mdi:av-timer'],      # Groupe horaire si option = heures creuses ou tempo : HHPHC(1 car.)
  'motdetat': ['Mot d etat', '', 'mdi:check'],        # Mot d’état(autocontrôle) : MOTDETAT(6 car.)
  'base': ['Base', 'Wh', ''],           # Index si option = base : BASE( 9 car.unité = Wh)
  'ejp hn': ['EJP Heures normales', 'Wh', ''],        # Index heures normales si option = EJP : EJP HN( 9 car.unité = Wh)</para>
  'ejp hpm': ['EJP Heures de pointe', 'Wh', ''],        # Index heures de pointe mobile si option = EJP : EJP HPM( 9 car.unité = Wh)</para>
  'pejp': ['EJP Préavis', 'Wh', ''],          # Préavis EJP si option = EJP : PEJP( 2 car.) 30mn avant période EJP</para>
  'bbr hc jb': ['Tempo heures bleues creuses', 'Wh', ''],     # Index heures creuses jours bleus si option = tempo : BBR HC JB( 9 car.unité = Wh)</para>
  'bbr hp jb': ['Tempo heures bleues pleines', 'Wh', ''],     # Index heures pleines jours bleus si option = tempo : BBR HP JB( 9 car.unité = Wh)</para>
  'bbr hc jw': ['Tempo heures blanches creuses', 'Wh', ''],   # Index heures creuses jours blancs si option = tempo : BBR HC JW( 9 car.unité = Wh)</para>
  'bbr hp jw': ['Tempo heures blanches pleines', 'Wh', ''],   # Index heures pleines jours blancs si option = tempo : BBR HP JW( 9 car.unité = Wh)</para>
  'bbr hc jr': ['Tempo heures rouges creuses', 'Wh', ''],     # Index heures creuses jours rouges si option = tempo : BBR HC JR( 9 car.unité = Wh)</para>
  'bbr hp jr': ['Tempo heures rouges pleines', 'Wh', ''],     # Index heures pleines jours rouges si option = tempo : BBR HP JR( 9 car.unité = Wh)</para>
  'demain': ['Tempo couleur demain', '', ''],       # Couleur du lendemain si option = tempo : DEMAIN</para>
  'adps': ['Dépassement Puissance', '', ''],        # Avertissement de dépassement de puissance souscrite : ADPS( 3 car.unité = ampères) (message émis uniquement en cas de dépassement effectif, dans ce cas il est immédiat)</para>
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
  vol.Required(CONF_RESOURCES, default=[]):
    vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
})

def setup_platform(hass, config, add_entities, discovery_info=None):
  """Setup sensors"""
  DATA = TeleinfoData()
  entities = []

  for resource in config[CONF_RESOURCES]:
    sensor_type = resource.lower()

    if sensor_type not in SENSOR_TYPES:
      _LOGGER.warning(
        "Sensor type: %s does not appear in teleinfo",
        sensor_type)

    entities.append(TeleinfoSensor(DATA,sensor_type))

  add_entities(entities, True)

class TeleinfoSensor(Entity):
  """Implementation of the Teleinfo sensor."""

  def __init__(self, data, sensor_type):
    """Initialize the sensor."""
    self._type = sensor_type
    self._name = SENSOR_TYPES[sensor_type][0]
    self._unit = SENSOR_TYPES[sensor_type][1]
    self._state = STATE_UNKNOWN
    self.data = data

  @property
  def name(self):
    """Return the name of the sensor."""
    return self._name

  @property
  def icon(self):
    """Icon to use in the frontend, if any."""
    return SENSOR_TYPES[self._type][2]

  @property
  def state(self):
    """Return the state of the sensor."""
    return self._state

  @property
  def unit_of_measurement(self):
    """Return the unit of measurement of this entity, if any."""
    return self._unit

  def update(self):
    """Get the latest data from device and updates the state."""
    #_LOGGER.info("update name=", self._type)
    self.data.update()
    if not self.data.frame:
      _LOGGER.warn("no data from teleinfo!")
      return
    for info in self.data.frame:
      if self._type == info['header']:
        val = info['value']
        if (val.isdigit()):
          self._state = int(val)
        else:
          self._state = val
        break
    # _LOGGER.info("name=", self._name,"state=",self._state)

class TeleinfoData:
  """Stores the data retrieved from Teleinfo.

  For each entity to use, acts as the single point responsible for fetching
  updates from the server.
  """

  def __init__(self):
    """Initialize the data object."""
    self._frame = None

  @property
  def frame(self):
    """Get latest update if throttle allows. Return status."""
    return self._frame

  @Throttle(MIN_TIME_BETWEEN_UPDATES)
  def update(self, **kwargs):
    """Fetch the latest status."""
    self._teleinfo = Teleinfo()
    self._teleinfo._open()
    self._frame = self._teleinfo._readFrame()
    self._teleinfo._close()

class TeleinfoError(Exception):
  """ Teleinfo related errors
  """


class Teleinfo():
  def __init__(self):
    """ """

  def _open(self):

    # Open a serial port on the FTDI device interface 
    #     'ftdi://ftdi:0x6001:C10593/1', 
    self.port = pyftdi.serialext.serial_for_url('/dev/serial/by-id/usb-Cartelectronic_Interface_USB_-__Compteur_C10593-if00-port0',
                  baudrate=1200,
                  parity=PARITY_EVEN,
                  bytesize=SEVENBITS,
                  stopbits=STOPBITS_ONE,
                  rtscts=1,
                  timeout=5)
    print('Port opened')

  def _close(self):
    self.port.close()

  def _readline(self):
    raw = u""
    try:
      while True:
        buf = self.port.read(1)
        c = buf.decode() #chr(ord(buf) % 0x80)  # Clear bit 7
        if c is not None and c != '\x00':
          raw += c
        if c == '\r' or c==ETX or c==STX:
          break

      raw = raw.replace('\r', '').replace('\n', '')
      #print('raw=',raw)
      return raw
    except Exception as e:
      print("Error in readline: %s",e)
      return ""

  def _readFrame(self):

    self.port.reset_input_buffer()
    checked_ok = False
    datas = []
    while not checked_ok:
      #print('wait STX')
      line = self._readline()
      while STX not in line:
        line = self._readline()
      #print('STX found')
      line = self._readline()
      while ETX not in line:
        if (len(line)>2):
          #_LOGGER.info("Line %s" % line)
          checksum = line[-1]
          header, value = line[:-2].split()
          if self._checkData(line, checksum):
            data = {'header': header.lower(), 'value': value, 'checksum': checksum}
            #print('append:',data)
            datas.append(data)
            checked_ok = True
          else:
            print('checksum error')
            break
        line = self._readline()

    return datas

  def _checkData(self, line, checksum):
    # Check entry
    sum = 0x0  # Space between header and value
    for c in line[:-2]:
      sum += ord(c)
    sum %= 0x40  # Checksum on 6 bits
    sum += 0x20  # Ensure printable char
    #print(line,"sum=",hex(sum),"chk=",hex(ord(checksum)))

    if sum != ord(checksum):
      return False

    return True


def main():
  #try:

    frame = [{'header': 'ADCO', 'value': '040422128707', 'checksum': '<'}]
    state = ''
    type = 'ADCO'
    for info in frame:
      if type == info['header']:
        state = info['value']
        break
    print(state)
    return 
    teleinfo = Teleinfo()
    teleinfo._open()
    while True:
      datas = teleinfo._readFrame()
      print("datas:",datas)
    teleinfo._close()

  #except Exception as e:
  # print("Error : %s",e)

if __name__ == "__main__":
  main()
