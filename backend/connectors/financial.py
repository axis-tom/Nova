import csv
from typing import Dict, Any, List
from backend.connectors.base import DataConnector

class CSVImporter(DataConnector):
    """CSV 文件导入连接器，用于解析银行账单等财务数据"""
    name = "csv_importer"

    async def fetch(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """读取 CSV 文件并返回数据列表"""
        file_path = input_data.get("file_path")
        if not file_path:
            return {"data": [], "status": "error", "error": "Missing file_path"}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            return {"data": rows, "status": "success", "count": len(rows)}
        except Exception as e:
            return {"data": [], "status": "error", "error": str(e)}

    async def push(self, output_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """CSV 导入不支持推送"""
        raise NotImplementedError("CSV importer does not support push")