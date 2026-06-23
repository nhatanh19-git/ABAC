# Env/Context Cluster Report

- total_clusters: 18
- total_unique_texts: 29
- total_bundles: 86

## Cluster Summaries

### Cluster 0 — system (spatial)
- size: 5
- referenced_by_bundles: 76
- sample_members:
    - the academic information system
    - the learning management system
    - the visiting lecturer management system

### Cluster 1 — resource.course_id (other)
- size: 1
- referenced_by_bundles: 0
- sample_members:
    - resource.course_id IN subject.enrolled_courses

### Cluster 2 — 7:00 (temporal)
- size: 1
- referenced_by_bundles: 1
- sample_members:
    - 7:00 am and 5:25 pm

### Cluster 3 — environment.current_time (temporal)
- size: 1
- referenced_by_bundles: 0
- sample_members:
    - environment.current_time IN [07:00, 17:25]

### Cluster 4 — academic (spatial)
- size: 1
- referenced_by_bundles: 1
- sample_members:
    - the academic affairs or finance offices

### Cluster 5 — resource.approver (spatial)
- size: 4
- referenced_by_bundles: 0
- sample_members:
    - resource.approver IN (finance_office, finance_office)
    - resource.approver IN (unknown)
    - resource.approver IN (academic_affairs_office, finance_office, finance_office)

### Cluster 6 — has (other)
- size: 1
- referenced_by_bundles: 1
- sample_members:
    - it has been numbered , made official , and exported

### Cluster 7 — resource.contract_number (other)
- size: 1
- referenced_by_bundles: 0
- sample_members:
    - resource.contract_number IS NOT NULL

### Cluster 8 — year (other)
- size: 1
- referenced_by_bundles: 1
- sample_members:
    - the year

### Cluster 9 — number (temporal)
- size: 3
- referenced_by_bundles: 3
- sample_members:
    - only the total number of teaching hours for a visiting lecturer within the year does not exceed the prescribed limit
    - the total number of registered credits exceeds the prescribed limit
    - the number of registered civilian students reaches the prescribed capacity

### Cluster 10 — system', (temporal)
- size: 3
- referenced_by_bundles: 5
- sample_members:
    - {'category': 'environment', 'env_type': 'spatial_device', 'subcategory': 'device_type', 'trigger': 'in', 'phrase': 'the visiting lecturer management system', 'env_name': 'the visiting lecturer management system', 'env_value': None, 'full_value': 'in the visiting lecturer management system', 'ner_type': '', 'normalized': 'visiting_lecturer_management_system', 'namespace': 'environment.device.device_type:visiting_lecturer_management_system', 'data_type': 'location', 'method': 'rule+dep'}
    - {'category': 'environment', 'env_type': 'spatial_device', 'subcategory': 'device_type', 'trigger': 'in', 'phrase': 'the academic information system', 'env_name': 'the academic information system', 'env_value': None, 'full_value': 'in the academic information system', 'ner_type': '', 'normalized': 'academic_information_system', 'namespace': 'environment.device.device_type:academic_information_system', 'data_type': 'location', 'method': 'rule+dep'}
    - {'category': 'environment', 'env_type': 'temporal', 'subcategory': 'absolute', 'trigger': 'between', 'phrase': '7:00 am and 5:25 pm', 'env_name': None, 'env_value': {'operator': 'between', 'from': {'value': 0, 'unit': 'am'}, 'to': {'value': 25, 'unit': 'pm'}}, 'full_value': 'between 7:00 am and 5:25 pm', 'ner_type': 'TIME', 'normalized': '7:00_am_and_5:25_pm', 'namespace': 'environment.time.absolute:7:00_am_and_5:25_pm', 'data_type': 'time', 'method': 'rule+dep'}

### Cluster 11 — they (other)
- size: 1
- referenced_by_bundles: 1
- sample_members:
    - they owe tuition fees exceeding the prescribed limit

### Cluster 12 — they (other)
- size: 1
- referenced_by_bundles: 1
- sample_members:
    - they have not passed the prerequisites for that course

### Cluster 13 — subject.completed_courses (other)
- size: 1
- referenced_by_bundles: 0
- sample_members:
    - subject.completed_courses CONTAINS resource.prerequisite_course_ids

### Cluster 14 — courses (other)
- size: 1
- referenced_by_bundles: 1
- sample_members:
    - the courses have overlapping class schedules

### Cluster 15 — not (other)
- size: 1
- referenced_by_bundles: 0
- sample_members:
    - NOT (resource.course_A.schedule OVERLAPS resource.course_B.schedule)

### Cluster 16 — course (other)
- size: 1
- referenced_by_bundles: 2
- sample_members:
    - the course registration system which are currently

### Cluster 17 — system (other)
- size: 1
- referenced_by_bundles: 1
- sample_members:
    - the system has not been activated

## Notable Stats

- singletons: 14
- multi-member clusters: 4