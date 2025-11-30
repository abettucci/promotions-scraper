"""
Parser de términos y condiciones MEJORADO
Extrae información estructurada de los T&C de las promociones
"""
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import config

class TermsParser:
    def __init__(self):
        # Patrones mejorados para exclusiones - ya no usados, se usa extract_exclusions_improved directamente
        self.exclusion_patterns = []
        
        self.requirement_patterns = [
            r'(?:SOLO|ÚNICAMENTE|EXCLUSIVAMENTE)\s+(?:PARA|CON)\s+([^.]+)',
            r'(?:NIVEL|PAQUETE)\s+(\w+)',
            r'(?:REQUIERE|NECESITA|DEBE)\s+([^.]+)',
            r'(?:VÁLIDO|VALIDO)\s+PARA\s+([^.]+)',
        ]
        
        # Meses en español
        self.meses = {
            'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4,
            'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
            'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
        }
        
        self.days_pattern = r'(?:LUNES|MARTES|MIÉRCOLES|MIERCOLES|JUEVES|VIERNES|SÁBADO|SABADO|DOMINGO)'
    
    def parse(self, text: str) -> Dict:
        """
        Parsea el texto de términos y condiciones
        Retorna un diccionario estructurado
        """
        if not text:
            return self._empty_result()
        
        text_upper = text.upper().strip()
        text_lower = text.lower().strip()
        
        result = {
            'raw_text': text,
            'exclusions': self.extract_exclusions_improved(text_upper),
            'requirements': self.extract_requirements_improved(text_upper),
            'valid_days': self.extract_valid_days(text_upper),
            'tope': self.extract_tope(text_upper),
            'acumulable': self.extract_acumulable(text_upper),
        }
        
        # Extraer fechas de vigencia
        valid_from, valid_until = self.extract_validity_dates(text_upper)
        if valid_from:
            result['valid_from'] = valid_from
        if valid_until:
            result['valid_until'] = valid_until
        
        return result
    
    def extract_acumulable(self, text: str) -> Optional[bool]:
        """
        Determina si la promoción es acumulable con otras
        Retorna: True si es acumulable, False si no, None si no se menciona
        """
        # Buscar "NO ACUMULABLE"
        if re.search(r'NO\s+ACUMULABLE', text):
            return False
        
        # Buscar "ACUMULABLE"
        if re.search(r'ACUMULABLE', text):
            return True
        
        return None
    
    def extract_tope(self, text: str) -> str:
        """
        Extrae el tope de reintegro/descuento
        Retorna el tope formateado o "SIN TOPE" o vacío
        """
        # Buscar "SIN TOPE"
        if re.search(r'SIN\s+TOPE', text):
            return 'SIN TOPE'
        
        # Patrones para extraer tope con monto
        tope_patterns = [
            r'TOPE\s+(?:DE\s+)?(?:DESCUENTO|REINTEGRO|DEVOLUCIÓN|DEVOLUCION|MÁXIMO|MAXIMO|MENSUAL|SEMANAL|DIARIO)?\s*[:\s]*\$?\s*(\d+[\d.,]*)',
            r'TOPE\s*[:\s]*\$?\s*(\d+[\d.,]*)',
            r'\$?\s*(\d+[\d.,]*)\s+TOPE\s+(?:DE\s+)?(?:REINTEGRO|DEVOLUCIÓN|DEVOLUCION)',
            r'HASTA\s+\$?\s*(\d+[\d.,]*)\s+(?:DE\s+)?(?:REINTEGRO|DEVOLUCIÓN|DEVOLUCION|DESCUENTO)',
            r'MÁXIMO\s+(?:DE\s+)?(?:REINTEGRO|DEVOLUCIÓN|DEVOLUCION|DESCUENTO)\s+(?:DE\s+)?\$?\s*(\d+[\d.,]*)',
        ]
        
        for pattern in tope_patterns:
            match = re.search(pattern, text)
            if match:
                amount = match.group(1).replace('.', '').replace(',', '.')
                # Convertir a float y formatear
                try:
                    amount_num = float(amount)
                    return f"${amount_num:,.0f}".replace(',', '.')
                except:
                    return f"${amount}"
        
        return ''
    
    def extract_validity_dates(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrae el rango de fechas de vigencia
        Retorna: (valid_from, valid_until) en formato YYYY-MM-DD
        """
        valid_from = None
        valid_until = None
        
        # Patrón 1: "DESDE EL DD AL DD DE MES DE YYYY"
        pattern1 = r'DESDE\s+EL\s+(\d{1,2})\s+AL\s+(\d{1,2})\s+DE\s+(' + '|'.join(self.meses.keys()) + r')\s+DE\s+(\d{4})'
        match = re.search(pattern1, text)
        if match:
            day_from = int(match.group(1))
            day_until = int(match.group(2))
            month_name = match.group(3)
            year = int(match.group(4))
            month = self.meses[month_name]
            
            valid_from = f"{year}-{month:02d}-{day_from:02d}"
            valid_until = f"{year}-{month:02d}-{day_until:02d}"
            return (valid_from, valid_until)
        
        # Patrón 2: "HASTA EL DD/MM/YYYY" o "HASTA EL DD DE MES DE YYYY"
        pattern2 = r'HASTA\s+EL\s+(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})'
        match = re.search(pattern2, text)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))
            valid_until = f"{year}-{month:02d}-{day:02d}"
            return (valid_from, valid_until)
        
        # Patrón 3: "HASTA EL DD DE MES DE YYYY"
        pattern3 = r'HASTA\s+EL\s+(\d{1,2})\s+DE\s+(' + '|'.join(self.meses.keys()) + r')\s+DE\s+(\d{4})'
        match = re.search(pattern3, text)
        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            year = int(match.group(3))
            month = self.meses[month_name]
            valid_until = f"{year}-{month:02d}-{day:02d}"
            return (valid_from, valid_until)
        
        # Patrón 4: "DE MES DE YYYY" (todo el mes)
        pattern4 = r'(?:TODOS?\s+LOS?\s+(?:DÍAS?|' + self.days_pattern + r')\s+)?DE\s+(' + '|'.join(self.meses.keys()) + r')\s+DE\s+(\d{4})'
        match = re.search(pattern4, text)
        if match:
            month_name = match.group(1)
            year = int(match.group(2))
            month = self.meses[month_name]
            
            # Primer día del mes
            valid_from = f"{year}-{month:02d}-01"
            
            # Último día del mes
            if month in [1, 3, 5, 7, 8, 10, 12]:
                last_day = 31
            elif month in [4, 6, 9, 11]:
                last_day = 30
            else:  # Febrero
                # Verificar año bisiesto
                if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                    last_day = 29
                else:
                    last_day = 28
            
            valid_until = f"{year}-{month:02d}-{last_day:02d}"
            return (valid_from, valid_until)
        
        return (valid_from, valid_until)
    
    def extract_exclusions_improved(self, text: str) -> str:
        """
        Extrae productos/categorías excluidas de forma mejorada
        Retorna el texto completo de exclusiones
        """
        # Patrón mejorado que captura hasta el final de la oración (punto seguido de espacio o mayúscula)
        exclusion_pattern = r'QUEDAN EXCLUIDOS? DEL DESCUENTO[:\s]+([^\.]+(?:\.[A-Z]\.?[^\.]*)*?)(?:\.\s+[A-Z]|\.\s*$|$)'
        
        match = re.search(exclusion_pattern, text)
        if match:
            exclusion_text = match.group(1).strip()
            # Limpiar el texto final quitando punto final si existe
            exclusion_text = exclusion_text.rstrip('.')
            return exclusion_text
        
        # Si no encuentra el patrón principal, buscar otros patrones
        other_patterns = [
            r'(?:SE EXCLUYE[N]?|NO INCLUYE|NO VÁLIDO PARA|EXCLUYE)[:\s]+([^\.]+(?:\.[A-Z]\.?[^\.]*)*?)(?:\.\s+[A-Z]|\.\s*$|$)',
            r'EXCEPTO[:\s]+([^\.]+(?:\.[A-Z]\.?[^\.]*)*?)(?:\.\s+[A-Z]|\.\s*$|$)',
        ]
        
        for pattern in other_patterns:
            match = re.search(pattern, text)
            if match:
                exclusion_text = match.group(1).strip().rstrip('.')
                return exclusion_text
        
        return ''
    
    def extract_requirements_improved(self, text: str) -> str:
        """
        Extrae requisitos de forma mejorada (NO incluye exclusiones ni tope)
        Retorna un string con los requisitos separados por comas
        """
        requirements = []
        
        # 1. "VÁLIDA ÚNICAMENTE PARA VENTA MINORISTA" (capturar solo hasta la coma que inicia exclusión)
        match = re.search(r'VÁLIDA?\s+ÚNICAMENTE\s+PARA\s+([A-ZÁÉÍÓÚÑ\s]+?)(?:,\s*SE\s+EXCLU|\.|\s*$)', text)
        if match:
            req = match.group(1).strip()
            if len(req) > 3 and len(req) < 100 and 'EXCLU' not in req:
                requirements.append(req)
        
        # 2. "CONSUMO FAMILIAR"
        if re.search(r'(?:SOLO|EXCLUSIVO)\s+PARA\s+CONSUMO\s+FAMILIAR', text):
            requirements.append('CONSUMO FAMILIAR')
        
        # 3. "COMPRA MÍNIMA"
        min_purchase = re.search(r'COMPRA\s+MÍNIMA\s+(?:DE\s+)?\$?\s*(\d+[.,\d]*)', text)
        if min_purchase:
            amount = min_purchase.group(1).replace('.', '').replace(',', '.')
            requirements.append(f'COMPRA MÍNIMA ${amount}')
        
        # 4. Otros requisitos específicos (pero evitando exclusiones)
        specific_patterns = [
            r'EXCLUSIVO\s+PARA\s+CLIENTES\s+([A-ZÁÉÍÓÚÑ\s]+?)(?:\.|,)',
            r'REQUIERE\s+(?:MEMBRESÍA|TARJETA)\s+([A-ZÁÉÍÓÚÑ\s]+?)(?:\.|,)',
            r'SOLO\s+PARA\s+CLIENTES\s+([A-ZÁÉÍÓÚÑ\s]+?)(?:\.|,)',
        ]
        
        for pattern in specific_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                req_text = match.group(1).strip() if match.lastindex >= 1 else match.group(0).strip()
                # Verificar que no sea parte de exclusión
                if len(req_text) > 3 and len(req_text) < 100:
                    if not any(word in req_text.upper() for word in ['EXCLU', 'EXCEPTO']):
                        requirements.append(req_text.strip())
        
        # NO incluir TOPE ni SIN TOPE como requisito - eso es información del campo tope
        
        # Remover duplicados y limpiar
        unique_requirements = []
        seen = set()
        for req in requirements:
            req_clean = req.strip(' .,;').upper()
            if req_clean and req_clean not in seen:
                # Triple verificación: NO incluir nada que mencione exclusiones o tope
                bad_keywords = ['EXCLU', 'EXCEPTO', 'NO INCLUYE', 'NO VÁLIDO', 'NO APLICA', 'TOPE']
                if not any(word in req_clean for word in bad_keywords):
                    seen.add(req_clean)
                    unique_requirements.append(req.strip(' .,;'))
        
        # Unir con comas
        result = ', '.join(unique_requirements[:10])  # Máximo 10 items
        return result[:500] if result else ''  # Máximo 500 caracteres
    
    def extract_valid_days(self, text: str) -> List[str]:
        """Extrae los días válidos de la promoción"""
        days_map = {
            'LUNES': 'Lunes',
            'MARTES': 'Martes',
            'MIÉRCOLES': 'Miércoles',
            'MIERCOLES': 'Miércoles',
            'JUEVES': 'Jueves',
            'VIERNES': 'Viernes',
            'SÁBADO': 'Sábado',
            'SABADO': 'Sábado',
            'DOMINGO': 'Domingo',
        }
        
        days = []
        matches = re.finditer(self.days_pattern, text)
        for match in matches:
            day = match.group(0).upper()
            if day in days_map:
                days.append(days_map[day])
        
        # Si encuentra "TODOS LOS DÍAS"
        if re.search(r'TODOS\s+LOS\s+D[ÍI]AS', text):
            return ['Todos los días']
        
        return list(dict.fromkeys(days))  # Remover duplicados manteniendo orden
    
    def _empty_result(self) -> Dict:
        """Retorna resultado vacío"""
        return {
            'raw_text': '',
            'exclusions': '',
            'requirements': '',
            'valid_days': [],
            'valid_from': None,
            'valid_until': None,
            'tope': '',
            'acumulable': None,
        }

# Test
if __name__ == "__main__":
    parser = TermsParser()
    
    test_text = """
    PROMOCIÓN VÁLIDA DESDE EL 01 AL 30 DE NOVIEMBRE DE 2025.
    15% DE DESCUENTO EXCLUSIVO TODOS LOS LUNES Y MARTES DE NOVIEMBRE DE 2025.
    SIN TOPE. QUEDAN EXCLUIDOS DEL DESCUENTO: ELECTRODOMÉSTICOS, TELEFONÍA, 
    FOTOGRAFÍA, INFORMÁTICA, IMAGEN, SONIDO, LECHES INFANTILES Y MATERNIZADAS 
    ETAPAS 1 Y 2, CARNICERÍA (CARNE VACUNA, POLLO, CERDO Y EMBUTIDOS).
    NO ACUMULABLE CON OTRAS PROMOCIONES VIGENTES.
    EXCLUSIVO SOLO PARA CONSUMO FAMILIAR.
    """
    
    result = parser.parse(test_text)
    
    print("🔍 Resultado del parseo:")
    print(f"Exclusiones: {result['exclusions']}")
    print(f"Requisitos: {result['requirements']}")
    print(f"Días válidos: {result['valid_days']}")
    print(f"Fecha desde: {result.get('valid_from', 'N/A')}")
    print(f"Fecha hasta: {result.get('valid_until', 'N/A')}")
    print(f"Acumulable: {result.get('acumulable', 'N/A')}")
