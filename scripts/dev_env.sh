echo -e "\e[32mCreate virtualenv\e[0m"
python -m venv .venv
source .venv/bin/activate
echo -e "\e[32mInstall dependencies into virtualenv\e[0m"
pip install -e .[dev]
deactivate
echo -e "\e[32mFinshed\e[0m"
echo -e "\e[34mUse 'source .venv/bin/activate' to activate the virtualenv\e[0m"
