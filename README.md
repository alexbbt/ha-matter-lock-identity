# Matter Lock Identity

Name the person who unlocked a Matter door lock.

Matter tells Home Assistant which *slot* opened the lock. That slot number belongs to one lock. The same person is often a different slot on the next lock, and the lock usually does not send a name. This integration keeps a private map from those slots to the stable Matter user id, then gives each person one entity you can rename.

An unlock is identified from that map. The lock is not queried when the door opens, so the name is attached as soon as the event arrives.

## What you get

- One config entry. People are not separate instances of the integration.
- One sensor per person, named `Lock user` plus the Matter user id until you rename it.
- One unlock event per lock. It fires again when the same person unlocks again.
- A `matter_lock_identity_unlocked` event on the Home Assistant event bus.

The sensor state is `present` while that person still has a slot on a lock, and `absent` after they are removed. The entity stays, so the name you gave them stays too.

## What an unlock looks like

Identified unlocks include the name you set and the stable id:

| Attribute | Meaning |
| --- | --- |
| `user_name` | The entity name, after any rename |
| `user_unique_id` | Stable Matter user id, shared by every lock |
| `user_index` | Slot on this lock only |
| `method` | How the lock was opened, such as `keypad`, `aliro`, `remote`, or `manual` |
| `credential_type` | Kind of credential, such as `pin`, `fingerprint`, or `rfid`, when the lock sent one |
| `credential_index` | Which credential on that person, when the lock sent one |
| `identified` | `true` when a person was found |
| `lock_name` | Name reported by the lock |
| `node_id` | Matter node id of the lock |
| `source_node` | Remote node, when the lock sent one |

Unlocks from inside the door, or from a remote app, often arrive with no user. Those events still fire, with `identified` false and no `user_name`. A lock event that is not an unlock is ignored.

The integration never asks the lock for a PIN and never stores credential bytes. A user whose Matter id is `0` is skipped. That value is not a stable person id.

## Add it

The Matter integration has to be set up first. This integration uses that connection. It does not open a second one.

### HACS

1. In HACS, open Integrations, then Custom repositories.
2. Add `https://github.com/alexbbt/ha-matter-lock-identity` as an integration.
3. Download **Matter Lock Identity** and restart Home Assistant.
4. Go to Settings, Devices & services, Add integration, and choose Matter Lock Identity.

### Manual

Copy `custom_components/matter_lock_identity` into the `custom_components` directory of your Home Assistant configuration. Restart, then add the integration as above.

There is nothing to type in the setup form. Names, locks, and user ids are discovered after it is installed.

## Name people

After the first refresh, each person is a sensor on the Matter Lock Identity device. Open the sensor and rename it. The next unlock uses that name.

The default name is whatever the lock reports, when it reports one. Otherwise it is `Lock user` and the numeric id. Renaming does not change the id, so automations that use `user_unique_id` keep working.

Slot numbers are only a lookup. Do not key an automation on the slot.

Press **Refresh users** after you add or remove someone. The table is also read when the integration starts, every six hours, and when an unlock mentions a slot that is not in the table yet. That first unlock can still be anonymous. The refresh does not delay it. The following unlock is named once the slot is known.

A reader that uses some other identifier, such as a Home Key issuer id, is a different namespace. It is not matched to a Matter user id. Name that person in both places, or connect them with an automation of your own.

## Automations

Fire on every identified unlock:

```yaml
alias: Named person unlocked a lock
triggers:
  - trigger: event
    event_type: matter_lock_identity_unlocked
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.identified }}"
actions:
  - action: notify.persistent_notification
    data:
      title: "{{ trigger.event.data.lock_name }}"
      message: "{{ trigger.event.data.user_name }}"
```

Or match the name you assigned:

```yaml
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.user_name == 'Ada' }}"
```

The same person unlocking twice still produces two bus events. The lock's unlock event entity also changes state every time, because its state is the time of the event rather than the person's name.

To read the locks again from an automation, press the Refresh users button.

## Logs

```yaml
logger:
  logs:
    custom_components.matter_lock_identity: info
```

Identified unlocks are logged at info. Anonymous unlocks are logged at debug. Debug logs include slot numbers.

## Development

```bash
python -m pip install -r requirements-test.txt
pytest
ruff check .
ruff format --check .
```

The tests cover the slot map and the unlock parser. They do not need a lock, a Matter server, or Home Assistant.

## License

MIT. See [LICENSE](LICENSE).
