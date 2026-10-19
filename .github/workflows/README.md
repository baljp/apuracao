# Por que não há workflow aqui

O carimbo de versão dos arquivos (`programa/versionar.py`) roda **localmente,
antes de cada commit**, e não como GitHub Action.

Havia um workflow que fazia isso automaticamente, mas ele criava um segundo
commit a cada publicação — e esse commit disparava um novo build do Pages. Com
dois workflows por push, a fila de runners começou a acumular e o site passou a
levar mais de meia hora para atualizar. Numa noite de apuração isso é
inaceitável: uma correção precisa chegar em minutos.

Sem workflow nenhum, o GitHub Pages publica direto do `main`, que é o caminho
mais curto e o único que não depende de runner disponível.

Antes de publicar qualquer mudança nos arquivos do site:

    python3 programa/versionar.py
    git add -A && git commit && git push
