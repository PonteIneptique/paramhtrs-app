

## Install

From this root directory

```shell
pip install requirements.txt
flask db create
flask import source/n10.jsonl
```

You can change the default login (username: `password`, password: `qwerty`) 
by adding --admin-username and --admin-password to your `flask db create`.

## Import new data

```shell
flask import your.jsonl
```

## Run

From this root directory

```shell 
flask run
```