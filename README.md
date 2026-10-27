# Matter Lock Identity

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz)
[![ha_version](https://img.shields.io/badge/Home%20Assistant-2025.1%2B-blue.svg?style=for-the-badge)](https://www.home-assistant.io/)
[![version](https://img.shields.io/github/v/release/alexbbt/ha-matter-lock-identity?style=for-the-badge&color=purple)](https://github.com/alexbbt/ha-matter-lock-identity/releases)
[![license](https://img.shields.io/github/license/alexbbt/ha-matter-lock-identity?style=for-the-badge&color=red)](https://github.com/alexbbt/ha-matter-lock-identity/blob/main/LICENSE)
[![iot_class](https://img.shields.io/badge/iot_class-local_push-green.svg?style=for-the-badge)](https://developers.home-assistant.io/docs/creating_integration_manifest#iot-class)

Matter Lock Identity names the person who unlocks a Matter door lock.

The lock sends a slot number with the unlock. A slot is the user number on that lock. The same person can have a different slot on the next lock. The stable id is the Matter user unique id. This integration stores a map from each slot to that id. An unlock reads the map and does not query the lock.

You rename each person in Home Assistant. The next unlock uses that name. When the lock sends a name, that name is the first sensor name. If the lock sends no name, the sensor name is Lock user plus the numeric id. The id stays the same when you rename the sensor. A user id of 0 is ignored, because that value is not a person.

## Requirements

You need Home Assistant 2025.1.0 or later. The Matter integration must already be set up on that Home Assistant. At least one Matter door lock must be paired. The lock must send a user index on the unlock event.

## Installation

HACS is the Home Assistant Community Store. This repository is a custom repository, so you add the URL yourself. The button below opens that page on your Home Assistant.

<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=alexbbt&repository=ha-matter-lock-identity&category=integration" target="_blank"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

1. Open the button above, or go to HACS and then Integrations.
2. Open the menu at the top right.
3. Select Custom repositories.
4. Add `https://github.com/alexbbt/ha-matter-lock-identity`.
5. Select Integration.
6. Download Matter Lock Identity.
7. Restart Home Assistant.

To install without HACS, download the latest archive from the releases page. The archive contains `custom_components/matter_lock_identity`. Copy that folder into the `custom_components` directory of your Home Assistant configuration. Restart Home Assistant after the copy. You can also copy that same folder from a clone of this repository.

## Setup

The button below starts the setup flow for Matter Lock Identity. You can also go to Settings, then Devices & services, then Add integration. Search for Matter Lock Identity. Submit the flow.

<a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=matter_lock_identity" target="_blank"><img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Open your Home Assistant instance and start setting up a new integration." /></a>

There is no account and no field to fill. The integration reads locks from the Matter integration that is already running. Each person appears as a sensor on the Matter Lock Identity device. Unlock and Operator entities live on the same Matter lock device as the lock.

## People and events

Each person is one sensor. The state is `present` when that person has a slot on a lock. The state is `absent` when that person has no slot on any lock. The sensor remains after you remove the person from the locks. The name that you set remains with the sensor. Open the sensor to set the name.

Each Matter lock gets one Operator sensor. The state is the person who last unlocked that lock. The state is `Unknown` when the unlock had no person. History for that sensor is a list of names over time.

Each Matter lock also gets one unlock event. The event fires on every unlock, including a repeat by the same person. The event state is the time of the unlock. A refresh reads the user table from each available lock. The refresh runs when the integration starts and every six hours. The Refresh users button starts a refresh immediately.

If an unlock refers to a slot that is not in the map, that unlock has no person. The integration then starts a refresh. The next unlock of that slot includes the person. An unlock with no user index has no person. Many locks send no user index for an inside handle or a remote app. Use the user unique id or the sensor name in automations, because the slot number is different on each lock.

The unlock carries `user_name`, which is the sensor name after you rename it. It carries `user_unique_id`, which is the same Matter id on every lock. It carries `user_index`, which is the slot on this lock only. It carries `method`, for example `keypad`, `aliro`, `remote`, or `manual`. It carries `credential_type` when the lock sends one, for example `pin`, `fingerprint`, or `rfid`. It carries `credential_index` when the lock sends one.

`identified` is true when a person was found. `lock_name` is the name that the lock reports. `node_id` is the Matter node id of the lock. `source_node` is the remote node when the lock sends one. An event that is not an unlock is ignored. The integration does not read PIN codes.

Home Assistant builds the entity id from the name. After you rename the person to Ada, the ids look like this:

- `sensor.lock_user_1001`
- `sensor.side_door_operator`
- `event.side_door_unlock`
- `button.matter_lock_identity_refresh_users`

The number 1001 is an example. Your lock uses the id that it assigned.

## Automations

The event name is `matter_lock_identity_unlocked`. The examples use the person Ada, the id 1001, and a lock named Side door. Replace the name, the id, and the entity ids with yours.

```yaml
# Notify when a known person unlocks.
- alias: "Named person unlocked a lock"
  trigger:
    - platform: event
      event_type: matter_lock_identity_unlocked
  condition:
    - condition: template
      value_template: "{{ trigger.event.data.identified }}"
  action:
    - action: notify.persistent_notification
      data:
        title: "{{ trigger.event.data.lock_name }}"
        message: "{{ trigger.event.data.user_name }}"

# Match the name that you set.
- alias: "Ada unlocked a lock"
  trigger:
    - platform: event
      event_type: matter_lock_identity_unlocked
  condition:
    - condition: template
      value_template: "{{ trigger.event.data.user_name == 'Ada' }}"
  action:
    - action: notify.persistent_notification
      data:
        message: "Ada is home"

# Match the stable id. A rename does not change it.
- alias: "Lock user 1001 unlocked"
  trigger:
    - platform: event
      event_type: matter_lock_identity_unlocked
      event_data:
        user_unique_id: 1001
  action:
    - action: notify.persistent_notification
      data:
        message: "Known person unlocked {{ trigger.event.data.lock_name }}"

# An unlock with no person.
- alias: "Anonymous unlock"
  trigger:
    - platform: event
      event_type: matter_lock_identity_unlocked
  condition:
    - condition: template
      value_template: "{{ not trigger.event.data.identified }}"
  action:
    - action: notify.persistent_notification
      data:
        message: "{{ trigger.event.data.lock_name }} unlocked with no person"

# One lock, from its event entity. The state is the time, so it changes on every unlock.
- alias: "Side door unlocked"
  trigger:
    - platform: state
      entity_id: event.side_door_unlock
  action:
    - action: notify.persistent_notification
      data:
        message: >-
          {{ trigger.to_state.attributes.user_name
             or 'Someone' }} unlocked the side door

# Read the user tables again.
- alias: "Refresh lock users"
  trigger:
    - platform: time
      at: "03:00:00"
  action:
    - action: button.press
      target:
        entity_id: button.matter_lock_identity_refresh_users
```

## Logs

Add the block below to `configuration.yaml`. This sets the log level for this integration to debug. Identified unlocks are written at info level. Unlocks with no person are written at debug level.

```yaml
logger:
  default: warning
  logs:
    custom_components.matter_lock_identity: debug
```

## Privacy

Home Assistant stores the names in the entity registry on the host that runs Home Assistant. The integration reads the slot, the user unique id, and the name when the lock sends a name. It does not read PIN codes. It does not send data to a cloud service. The repository contains no names and no ids from a home.

## Issues

To report a fault, open an issue with the Home Assistant version and the integration version. Name the lock manufacturer and the lock model. Attach a debug log with names, ids, and codes removed.

If the lock never sends a user index, use the lock support issue form. The form asks for the manufacturer, the model, and the firmware. Do not include the serial number. A serial number identifies the lock in your home.

## Development

GitHub Actions runs the tests, ruff, and mypy on each push and each pull request. Hassfest and HACS validate the integration on the same events. A published release builds `matter_lock_identity.zip` and attaches it to the release. The tests do not need a lock, a Matter server, or Home Assistant.

1. Create a virtual environment with `python3 -m venv venv`.
2. Activate the environment with `source venv/bin/activate`.
3. Install pre-commit with `pip install pre-commit`.
4. Install the git hooks with `pre-commit install`.
5. Run `pre-commit run --all-files` before you commit.

The commands below run the same checks without the git hooks.

```bash
source venv/bin/activate
pip install -r requirements-test.txt
ruff check .
ruff format --check .
mypy custom_components
pytest
```

## License

This project uses the MIT License. The terms are in the LICENSE file. This project is not part of the Connectivity Standards Alliance, and it is not made by a lock manufacturer.
