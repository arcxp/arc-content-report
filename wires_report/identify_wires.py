import argparse
import csv
import os
import pathlib
import re
from dataclasses import dataclass

import requests
import tqdm
from ratelimit import limits, sleep_and_retry


@dataclass
class ReportItem:
    ans_id: str
    source: str
    published_copy: str
    created_date: str
    environment: str


class RunReport:
    def __init__(
        self,
        bearer_token: str=True,
        org: str=True,
        environment: bool=True,
        website: str=True,
        start_date: str=True,
        end_date: str=True,
        q_additional: str="",
        report_folder: str=True,
    ):
        self.dsl = False
        self.env = "production" if environment == "production" else "sandbox"
        self.org = org if self.env == "production" else f"sandbox.{org}"
        self.website = str(website),
        self.bearer_token = bearer_token
        self.start_date = start_date,
        self.end_date = end_date,
        self.q_additional = q_additional,
        self.from_next = 0
        self.report_items = []
        self.report_count = None
        self.report_folder = report_folder
        self.scan_count = 0
        os.environ["ENVIRONMENT"] = self.env
        self.pbar = None
        self.current_ans_id = ""

        client_kwargs = {}

        self.arc_auth_header = {"Authorization": f"Bearer {self.bearer_token}", "User-Agent": f"python-requests-{self.org}-script-arcxp"}

    @property
    def search_url(self) -> str:
        return f"https://api.{self.org}.arcpublishing.com/content/v4/search"

    @property
    def search_q(self) -> str:
        return f"type:story AND revision.published:false {self.q_additional[0]} AND source.source_type:wires AND created_date:[{self.start_date[0]} TO {self.end_date[0]}]"

    @property
    def search_dsl(self) -> str:
        # build this method if you want to pass in a DSL query instead of a q filter.  You'll need to add a way to set self.dsl
        return f""

    @sleep_and_retry
    @limits(calls=20, period=60)
    def search(self):
        # search endpoint is limited to 10k records and no "from" value greater than 5000
        # error when query result is too big is like
        # {'message': '[illegal_argument_exception] Result window is too large, from + size must be less than or equal to: [10000] but was [10100]. See the scroll api for a more efficient way to request large data sets.'}
        params = {
            "_sourceInclude": "_id,source.name,created_date,revision.published,additional_properties.has_published_copy",
            "website": self.website,
            "track_total_hits": "true",
            "q": self.search_q,
            "size": "100",
            "from": self.from_next
        }

        if self.dsl:
            params.pop("q")
            params["body"] = self.search_dsl
        res = requests.request("GET", self.search_url,  headers=self.arc_auth_header, params=params)

        data = res.json()
        if res.ok:
            # self.from_next = data.get("next") if data.get("next", None) else self.from_next + 1
            self.from_next += 100
            # try:
            #     # are there more results to page through?
            #     if data.get("next"):
            #         self.from_next = data["next"]
            # except Exception as e:
            #     print("a", e)

            # set the total in the progress bar
            if not self.scan_count:
                self.pbar.total = data["count"]

            # build list of items
            for row in data.get("content_elements"):
                self.scan_count += 1
                self.pbar.update(1)
                self.current_ans_id = row["_id"]
                item = ReportItem(
                    row["_id"],
                    row.get("source", {}).get("name", ""),
                    row.get("additional_properties", {}).get("has_published_copy", ""),
                    row["created_date"],
                    self.env
                )

                self.report_items.append(item.__dict__)

            try:
                # paginate
                if self.scan_count < self.pbar.total:
                    self.search()
                else:
                    data.pop("content_elements", None)
            except Exception as e:
                print("search exception", self.current_ans_id, e)

        else:
            print('something broke', self.current_ans_id, res.status_code)
            print(data)

    def write_it_out(self, report_items, report_name):
        header = ["ans_id","source", "published_copy", "created_date", "environment"]

        fw = open(f"{self.report_folder}/{report_name}.csv", "w")
        writer = csv.DictWriter(fw, fieldnames=header)
        writer.writeheader()
        for row in report_items:
            writer.writerow(row)
        return report_items

    def report(self):
        print(f"starting {self.start_date[0]} to {self.end_date[0]} {self.env.upper()} {self.q_additional}")
        try:
            # visual progress bar, initialize
            self.pbar = tqdm.tqdm(total=0)
            self.search()
            self.pbar.close()
        except Exception as e:
            print(self.current_ans_id, e)
        finally:
            report_name = f"{self.start_date[0]}_{self.end_date[0]}"
            if len(self.q_additional[0]):
                report_name = report_name + f"_{re.sub(r'[^A-Za-z0-9]', '_', self.q_additional[0])}"
            report = self.write_it_out(self.report_items, report_name)

        # we're done
        return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--org",
        dest="org",
        help="arc xp organization id",
        required=True
    )
    parser.add_argument(
        "--environment",
        dest="environment",
        help="production or sandbox",
        default="production"
    )
    parser.add_argument(
        "--bearer-token",
        dest="bearer_token",
        help="bearer token to match the environment and organization",
        required=True
    )
    parser.add_argument(
        "--website",
        dest="website",
        help="organization website for the elastic search query to search",
        required=True
    )
    parser.add_argument(
        "--start-date",
        dest="start_date",
        help="start date in this format: 2020-01-01",
        default="2020-01-01"
    )
    parser.add_argument(
        "--end-date",
        dest="end_date",
        help="end date in this format: 2020-01-31",
        default="2020-01-01"
    )
    parser.add_argument(
        "--q-additional",
        dest="q_additional",
        help="query param to limit the search, needed in case one day of results is still over 10k results",
        default=""
    )
    current_dir = str(pathlib.Path().resolve())
    parser.add_argument(
        "--report-folder",
        dest="report_folder",
        help="file path to the folder where csvs will be created, no trailing slash",
        default=f"{current_dir}/spreadsheets"
    )
    args = parser.parse_args()
    print(args)

    # If you want to run several timeframes serially, use this data structure
    # tuple structure: (date from, date to, additional query filter to send to elasticsearch)
    dates = [
        # ('2025-01-02', '2025-01-02', 'AND source.name:Washington Post'),
        # ('2025-01-01', '2025-01-07', ''),
        # ('2025-01-08', '2025-01-14', ''),
        # ('2025-01-22', '2025-01-29', ''),
        # ('2025-01-30', '2025-01-31', ''),
    ]

    if dates:
        # Run it #1: from hard coded array of tuples
        print("running from tuples of dates")
        for d in dates:
            RunReport(bearer_token=args.bearer_token, org=args.org, environment=args.environment, website=args.website,  q_additional=d[2], start_date=d[0], end_date=d[1], report_folder=args.report_folder).report()
    else:
        # Run it #2: from the arguments
        print("running from arguments")
        RunReport(bearer_token=args.bearer_token, org=args.org, environment=args.environment, website=args.website, q_additional=args.q_additional, start_date=args.start_date, end_date=args.end_date, report_folder=args.report_folder).report()


# import individual csvs into excel to create one excel document, using excel's import abilities

## Not necessary, but I found renaming the files in the terminal helpful for the next step, smooshing them together in excel
# paste below in the terminal to rename all files in a folder from containing _2025- to _to_
## add echo mv to see what the rename will be instead of doing a full send
# for file in *_2025*; do
#   newname="${file//_2025-/_to_}"
#   mv "$file" "$newname"
# done