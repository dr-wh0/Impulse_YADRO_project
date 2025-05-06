import json
import xml.etree.ElementTree as ET
from typing import Dict, List


class XMLProcessor:
    def __init__(self, xml_content: str):
        self.xml_content = xml_content
        self.classes = self._parse_xml_classes()

    def _parse_xml_classes(self) -> Dict[str, Dict]:
        tree = ET.ElementTree(ET.fromstring(self.xml_content))
        root = tree.getroot()

        classes = {}

        # Обработка классов
        for elem in root.findall('Class'):
            class_name = elem.get('name')
            classes[class_name] = {
                'isRoot': elem.get('isRoot') == 'true',
                'documentation': elem.get('documentation', ''),
                'attributes': [
                    {'name': a.get('name'), 'type': a.get('type')}
                    for a in elem.findall('Attribute')
                ],
                'children': []
            }

        # Обработка агрегаций
        for agg in root.findall('Aggregation'):
            source = agg.get('source')
            target = agg.get('target')
            source_mult = agg.get('sourceMultiplicity')

            if target in classes:
                classes[target]['children'].append({
                    'name': source,
                    'multiplicity': source_mult
                })

        return classes

    def build_xml_structure(self, current_class: str) -> ET.Element:
        class_info = self.classes[current_class]
        element = ET.Element(current_class)

        # Добавление атрибутов
        for attr in class_info['attributes']:
            attr_element = ET.Element(attr['name'])
            attr_element.text = attr['type']
            element.append(attr_element)

        # Добавление дочерних классов
        for child in class_info['children']:
            child_element = self.build_xml_structure(child['name'])
            element.append(child_element)

        return element

    def generate_config_xml(self) -> str:
        # Поиск корневого класса
        root_class = None
        for class_name, class_info in self.classes.items():
            if class_info['isRoot']:
                root_class = class_name
                break

        if not root_class:
            raise ValueError("Не найден root (корневой класс) в XML")

        root_element = self.build_xml_structure(root_class)
        ET.indent(root_element, space="    ")
        return ET.tostring(root_element, encoding='unicode')

    def generate_meta_json(self) -> List[Dict]:
        tree = ET.ElementTree(ET.fromstring(self.xml_content))
        root = tree.getroot()

        # Мощность (multiplicity) для каждого класса
        class_multiplicity = {}
        for agg in root.findall('Aggregation'):
            source = agg.get('source')
            source_mult = agg.get('sourceMultiplicity')

            if '..' in source_mult:
                min_s, max_s = source_mult.split('..')
            else:
                min_s = max_s = source_mult

            class_multiplicity[source] = {'max': max_s, 'min': min_s}

        meta_data = []
        for class_name, class_info in self.classes.items():
            entry = {
                'class': class_name,
                'documentation': class_info['documentation'],
                'isRoot': class_info['isRoot']
            }

            # min/max
            if class_name in class_multiplicity and not class_info['isRoot']:
                entry['max'] = class_multiplicity[class_name]['max']
                entry['min'] = class_multiplicity[class_name]['min']

            # Параметры
            entry['parameters'] = [
                {'name': attr['name'], 'type': attr['type']}
                for attr in class_info['attributes']
            ]

            # Дочерние классы как параметры
            for child in class_info['children']:
                entry['parameters'].append({
                    'name': child['name'],
                    'type': 'class'
                })

            meta_data.append(entry)

        return meta_data


class ConfigDeltaProcessor:
    @staticmethod
    def generate(config_json: Dict, patched_config_json: Dict) -> Dict:
        delta = {
            'additions': [],
            'deletions': [],
            'updates': []
        }

        for key, value in patched_config_json.items():
            if key not in config_json:  # Поиск добавлений
                delta['additions'].append({
                    'key': key,
                    'value': value
                })

        for key in config_json.keys():
            if key not in patched_config_json:  # Поиск удалений
                delta['deletions'].append(key)

        for key in config_json:
            if key in patched_config_json and config_json[key] != patched_config_json[key]:  # Поиск обновлений
                delta['updates'].append({
                    'key': key,
                    'from': config_json[key],
                    'to': patched_config_json[key]
                })
        return delta

    @staticmethod
    def apply(config_json: Dict, delta: Dict) -> Dict:
        result = config_json.copy()

        for key in delta['deletions']:
            if key in result:
                del result[key]

        for update in delta['updates']:
            if update['key'] in result:
                result[update['key']] = update['to']

        for addition in delta['additions']:
            result[addition['key']] = addition['value']

        return result


class ConfigGenerator:
    def __init__(self, input_dir='./input', output_dir='./out'):
        self.input_dir = input_dir
        self.output_dir = output_dir

    def run(self):
        # Чтение файлов
        with open(f'{self.input_dir}/impulse_test_input.xml', 'r') as f:
            xml_content = f.read()

        with open(f'{self.input_dir}/config.json', 'r') as f:
            config_json = json.load(f)

        with open(f'{self.input_dir}/patched_config.json', 'r') as f:
            patched_config_json = json.load(f)

        # Обработка XML
        xml_processor = XMLProcessor(xml_content)

        # Генерация файлов
        with open(f'{self.output_dir}/config.xml', 'w') as f:
            f.write(xml_processor.generate_config_xml())

        with open(f'{self.output_dir}/meta.json', 'w') as f:
            json.dump(xml_processor.generate_meta_json(), f, indent=4)

        delta = ConfigDeltaProcessor.generate(config_json, patched_config_json)
        with open(f'{self.output_dir}/delta.json', 'w') as f:
            json.dump(delta, f, indent=4)

        result_config = ConfigDeltaProcessor.apply(config_json, delta)
        with open(f'{self.output_dir}/res_patched_config.json', 'w') as f:
            json.dump(result_config, f, indent=4)


if __name__ == '__main__':
    ConfigGenerator().run()