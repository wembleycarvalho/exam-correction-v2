"""
Monitor and manage Connect chat sessions.
Usage:
  source .env && python3 scripts/manage_sessions.py          # List active sessions
  source .env && python3 scripts/manage_sessions.py kill      # Kill all active sessions
  source .env && python3 scripts/manage_sessions.py kill ID   # Kill specific session
"""
import boto3
import json
import sys
import datetime

REGION = 'us-east-1'
INSTANCE_ID = '82a1c25d-b923-4bd2-9c21-e7eba7f052ac'

connect = boto3.client('connect', region_name=REGION)

def list_sessions():
    now = datetime.datetime.utcnow()
    start = now - datetime.timedelta(hours=24)

    resp = connect.search_contacts(
        InstanceId=INSTANCE_ID,
        TimeRange={
            'Type': 'INITIATION_TIMESTAMP',
            'StartTime': start,
            'EndTime': now
        },
        SearchCriteria={
            'Channels': ['CHAT']
        },
        MaxResults=50
    )

    contacts = resp.get('Contacts', [])
    active = []
    ended = []

    for c in contacts:
        has_disconnect = c.get('DisconnectTimestamp') is not None
        if has_disconnect:
            ended.append(c)
        else:
            active.append(c)

    print(f'=== Active Chat Sessions: {len(active)} ===')
    for c in active:
        init_time = c.get('InitiationTimestamp', '?')
        method = c.get('InitiationMethod', '?')
        print(f'  ID: {c["Id"]}')
        print(f'  Started: {init_time} | Method: {method}')
        print()

    print(f'=== Ended Sessions (last 24h): {len(ended)} ===')
    return active


def kill_session(contact_id):
    try:
        connect.stop_contact(
            ContactId=contact_id,
            InstanceId=INSTANCE_ID
        )
        print(f'  Killed: {contact_id}')
    except Exception as e:
        print(f'  Error killing {contact_id}: {e}')


def kill_all(active):
    if not active:
        print('No active sessions to kill.')
        return
    print(f'Killing {len(active)} sessions...')
    for c in active:
        kill_session(c['Id'])


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'list'

    if action == 'list':
        list_sessions()
    elif action == 'kill':
        active = list_sessions()
        if len(sys.argv) > 2:
            kill_session(sys.argv[2])
        else:
            kill_all(active)
    else:
        print(f'Unknown action: {action}')
        print('Usage: manage_sessions.py [list|kill] [contact_id]')
