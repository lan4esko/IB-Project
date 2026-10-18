"""Daily local planning job. No OpenProject API credentials needed."""
import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from app.automation import plan
from app.db import SessionLocal


def main():
    parser=argparse.ArgumentParser(description='OI Registry local control planner (never sends OpenProject tasks)')
    parser.add_argument('--dry-run',action='store_true',help='do not write to the database')
    parser.add_argument('--as-of',help='local test date, YYYY-MM-DD')
    args=parser.parse_args()
    from datetime import date
    from app.main import LOCAL_TIMEZONE
    today=date.fromisoformat(args.as_of) if args.as_of else datetime.now(LOCAL_TIMEZONE).date()
    with SessionLocal() as db:
        result=plan(db,today,write=not args.dry_run)
        print(json.dumps(result,ensure_ascii=False,default=str,indent=2))

if __name__=='__main__':main()
