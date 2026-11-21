sqlite3 <dbName> //to initialize the db
.read <sqlFile> //to execute a sql file

sqlite3 <dbName> < <sqlFile> //to execute sql file outside sqlite terminal

//for initializing a virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt