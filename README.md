[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)

# HA Telesensor
Permet de récupérer les données TeleSensor sur HomeAssistant (http://www.home-assistant.io)

## Requis
  Package pyftdi version 0.29.3 minimum


## Utilisation

Dans le fichier sensor.yaml :

```yaml
	- platform: teleinfo
	  resources:
	  - iinst
	  - imax
	  - papp
	  - ptec
```

## Licence 

[Lire la licence](LICENSE)
