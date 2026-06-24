:: Cria o ambiente virtual dentro da pasta do projeto
python -m venv .venv

:: Ativa o ambiente virtual no Windows
.venv\Scripts\activate

:: Atualiza o pip para evitar erro bobo de instalação
python -m pip install --upgrade pip