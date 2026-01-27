"""
Carregador de Documentos.

Suporta carregamento de contratos em diferentes formatos:
- PDF (.pdf)
- Word (.docx)
- Texto plano (.txt)
"""

import re
from pathlib import Path
from typing import IO


class DocumentLoader:
    """
    Carregador de documentos contratuais.

    Suporta múltiplos formatos de arquivo e extração de texto.
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}

    def __init__(self):
        """Inicializa o carregador."""
        pass

    def load(self, file_path: str | Path) -> str:
        """
        Carrega um documento e retorna seu texto.

        Args:
            file_path: Caminho para o arquivo

        Returns:
            Texto extraído do documento

        Raises:
            ValueError: Se formato não suportado
            FileNotFoundError: Se arquivo não existe
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        ext = path.suffix.lower()

        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Formato não suportado: {ext}. "
                f"Formatos suportados: {self.SUPPORTED_EXTENSIONS}"
            )

        if ext == ".pdf":
            return self._load_pdf(path)
        elif ext in {".docx", ".doc"}:
            return self._load_docx(path)
        elif ext in {".txt", ".md"}:
            return self._load_text(path)

        return ""

    def _load_pdf(self, path: Path) -> str:
        """Carrega texto de PDF."""
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(path))
            text_parts = []

            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            return "\n\n".join(text_parts)

        except ImportError:
            raise ImportError(
                "PyPDF2 não instalado. Instale com: pip install PyPDF2"
            )

    def _load_docx(self, path: Path) -> str:
        """Carrega texto de DOCX."""
        try:
            from docx import Document

            doc = Document(str(path))
            paragraphs = []

            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)

            return "\n\n".join(paragraphs)

        except ImportError:
            raise ImportError(
                "python-docx não instalado. Instale com: pip install python-docx"
            )

    def _load_text(self, path: Path) -> str:
        """Carrega texto de arquivo texto."""
        encodings = ["utf-8", "latin-1", "cp1252"]

        for encoding in encodings:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue

        # Fallback com erros ignorados
        return path.read_text(encoding="utf-8", errors="ignore")

    def load_from_string(self, text: str) -> str:
        """
        Processa texto bruto.

        Útil quando o texto já foi extraído de outra fonte.
        """
        # Normalizar quebras de linha
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Remover múltiplas linhas em branco consecutivas
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()


def load_document(file_path: str | Path) -> str:
    """
    Função utilitária para carregar documento.
    """
    loader = DocumentLoader()
    return loader.load(file_path)
