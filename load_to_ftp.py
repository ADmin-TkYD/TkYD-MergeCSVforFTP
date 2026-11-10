from __future__ import annotations

import asyncio
import aioftp
from pathlib import Path
from typing import Dict, Any, List

from logger import logging
from config import Config

logging = logging.getLogger(__name__)


async def upload_file_to_ftp(local_path: str, remote_path: str) -> Dict[str, Any]:
    """
    Асинхронная функция загрузки файла на FTP сервер.

    :param local_path: путь к локальному файлу для загрузки
    :param remote_path: путь на FTP-сервере (включая имя файла)
    :return: словарь с информацией о результате загрузки
    """
    ftp_cfg: Dict[str, str | int] = Config().get_config('ftp')
    host = ftp_cfg.get('ftp_host', '')
    port = int(ftp_cfg.get('ftp_port', 21) or 21)
    user = ftp_cfg.get('ftp_user', '')
    password = ftp_cfg.get('ftp_pass', '')

    if not host or not user or not password:
        raise ValueError('FTP host, user и password должны быть заданы в конфигурации (ftp)')

    if not Path(local_path).is_file():
        raise FileNotFoundError(f'Локальный файл не найден: {local_path}')

    str(remote_path).rstrip('/')

    async with aioftp.Client.context(host, port=port, user=user, password=password) as client:
        await client.upload(local_path, remote_path, write_into=True)

    result = {'local': local_path, 'remote': remote_path, 'status': 'success'}

    logging.debug(f'Upload on FTP result: {result}')

    return result


async def list_files_on_ftp(remote_path: str = '/') -> List[str]:
    """
    Асинхронно вернуть список путей на FTP-сервере рекурсивно под указанным remote_path.

    :param remote_path: путь на FTP-сервере.

    :return: Возвращает список строк (путь на FTP). При отсутствии пути или ошибки доступа — пустой список.
    """
    ftp_cfg = Config().get_config('ftp')
    host = str(ftp_cfg.get('ftp_host', ''))
    port = int(str(ftp_cfg.get('ftp_port', 21)) or 21)
    user = str(ftp_cfg.get('ftp_user', ''))
    password = str(ftp_cfg.get('ftp_pass', ''))

    if not host or not user or not password:
        logging.error('FTP конфигурация недостаёт: host, user или password не заданы (раздел ftp).')
        return []

    if not remote_path:
        remote_path = '/'

    results: List[str] = []
    try:
        async with aioftp.Client.context(host, port=port, user=user, password=password) as client:
            logging.info(f'Recursive listing FTP path: {remote_path}')
            async for path, info in client.list(remote_path, recursive=True):
                results.append(str(path))
    except Exception as e:
        # Логируем и безопасно возвращаем пустой список, если путь не существует
        msg = str(e).lower()
        if '550' in msg or 'not found' in msg or 'no such file' in msg:
            logging.warning(f'FTP path not found or inaccessible: {remote_path}')
            return []
        logging.exception(f'FTP listing error for {remote_path}: {e}')
        return []

    return results


async def find_matching_files(directory_path: str, filename_pattern: str) -> Dict[str, Dict[str, float]]:
    """
    Асинхронная функция поиска файлов в каталоге по шаблону, используя Path.
    :param directory_path: корневой каталог для поиска
    :param filename_pattern: маска файла (например '*.txt')
    :return: словарь: путь -> {'size': ..., 'mtime': ...}
    """

    def _collect_matching_paths() -> List[Path]:
        root_dir = Path(directory_path)
        # Рекурсивный поиск файлов, имя файла соответствует pattern
        return [matched_path for matched_path in root_dir.rglob(filename_pattern) if matched_path.is_file()]

    matching_paths = await asyncio.to_thread(_collect_matching_paths)

    results: Dict[str, Dict[str, float]] = {}
    for file_path in matching_paths:
        stats = file_path.stat()
        results[str(file_path)] = {'size': float(stats.st_size), 'mtime': float(stats.st_mtime)}
    return results


if __name__ == '__main__':
    async def main(max_concurrency: int = 1):
        # Пример: нашли все *.txt в директории 'incoming'
        matches_files = await find_matching_files('incoming', '*.txt')
        if not matches_files:
            logging.info('No matching files found in directory: incoming/*.txt')
            return

        sem = asyncio.Semaphore(max_concurrency)

        async def _upload_with_sem(local_path: str, remote_path: str):
            async with sem:
                try:
                    await upload_file_to_ftp(local_path, remote_path)
                    logging.info(f'Uploaded {local_path} -> {remote_path}')
                except Exception as e:
                    logging.exception(f'Failed to upload {local_path}: {e}')

        tasks = [
            asyncio.create_task(
                _upload_with_sem(local_path, f'/uploads/{Path(local_path).name}')
            )
            for local_path in matches_files.keys()
        ]
        # tasks.append(asyncio.create_task(list_files_on_ftp()))

        if tasks:
            await asyncio.gather(*tasks)

        list_paths = await list_files_on_ftp('/uploads')
        for path in list_paths:
            print(path)

    asyncio.run(main())
