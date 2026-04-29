# -*- coding: utf-8 -*-
import hashlib

senha = "123456"
print(hashlib.sha256(senha.encode()).hexdigest())