### JHU Course Evaluation Crawler & Visualization GUI

### How to run:

#### Crawler:

To run the crawler, have 2 terminals open. Download [Export Cookies](https://addons.mozilla.org/en-US/firefox/addon/export-cookies-txt/) for Firefox (TODO: Find similar plugin for Chrome). 

Once downloaded, go to the [course evaluation website](https://asen-jhu.evaluationkit.com/Report/Public) and search some course code (e.g. AS.), once the results appear export cookies for "asen-jhu.evaluationkit.com" and store it next to eval_crawler.py and rename to cookies.txt.

Run on the first terminal:

```
python eval_crawler.py --live
```

Run on the second terminal:

```
python extract.py
```

Results will be stored in all_course_stats.csv.

#### GUI:

Put the extracted and parsed csv file under course_dashboard/app/data/ and make sure it is named all_course_stats.csv.

In the course_dashboard directory for the first time run:

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python preprocess.py
python run.py
```

Later just run

```
python run.py
```

Unless data is modified.