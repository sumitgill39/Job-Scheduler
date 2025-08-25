"""
ADO.NET-Style Disconnected Data Manager for SQL Server
Similar to C# DataSet/DataTable pattern - eliminates connection pooling issues
"""

import pyodbc
import time
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager


@dataclass
class DataTable:
    """Python equivalent of ADO.NET DataTable"""
    name: str
    columns: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    primary_key: str = None
    modified_rows: Dict[str, Dict] = field(default_factory=dict)
    deleted_rows: List[Dict] = field(default_factory=list)
    new_rows: List[Dict] = field(default_factory=list)
    is_dirty: bool = False
    row_state: Dict[str, str] = field(default_factory=dict)  # Track row states like C#
    
    def add_row(self, row_data: Dict[str, Any]) -> str:
        """Add new row to table (like DataTable.Rows.Add)"""
        # Generate temporary key for new rows
        temp_key = f"NEW_{int(time.time() * 1000000)}"
        
        # Add system fields if not present
        if 'created_date' not in row_data:
            row_data['created_date'] = datetime.now()
        if 'modified_date' not in row_data:
            row_data['modified_date'] = datetime.now()
            
        self.rows.append(row_data)
        self.new_rows.append(row_data)
        self.row_state[temp_key] = 'Added'
        self.is_dirty = True
        
        return temp_key
    
    def update_row(self, key_value: Any, updates: Dict[str, Any]) -> bool:
        """Update existing row (like DataRow item assignment)"""
        for row in self.rows:
            if row.get(self.primary_key) == key_value:
                # Apply updates
                row.update(updates)
                row['modified_date'] = datetime.now()
                
                # Track modification
                self.modified_rows[key_value] = row
                self.row_state[str(key_value)] = 'Modified'
                self.is_dirty = True
                return True
        return False
    
    def delete_row(self, key_value: Any) -> bool:
        """Mark row for deletion (like DataRow.Delete)"""
        for i, row in enumerate(self.rows):
            if row.get(self.primary_key) == key_value:
                deleted_row = self.rows.pop(i)
                self.deleted_rows.append(deleted_row)
                self.row_state[str(key_value)] = 'Deleted'
                self.is_dirty = True
                return True
        return False
    
    def select(self, filter_func: Callable = None, order_by: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """Select rows with optional filtering (like DataTable.Select)"""
        filtered_rows = self.rows.copy()
        
        # Apply filter
        if filter_func:
            filtered_rows = [row for row in filtered_rows if filter_func(row)]
        
        # Apply ordering
        if order_by:
            reverse = order_by.startswith('-')
            order_field = order_by.lstrip('-')
            filtered_rows.sort(key=lambda x: x.get(order_field, ''), reverse=reverse)
        
        # Apply limit
        if limit:
            filtered_rows = filtered_rows[:limit]
            
        return filtered_rows
    
    def find(self, key_value: Any) -> Optional[Dict[str, Any]]:
        """Find row by primary key (like DataTable.Rows.Find)"""
        if not self.primary_key:
            return None
            
        for row in self.rows:
            if row.get(self.primary_key) == key_value:
                return row
        return None
    
    def get_changes(self) -> Dict[str, List[Dict]]:
        """Get all changes (like DataTable.GetChanges)"""
        return {
            'added': self.new_rows.copy(),
            'modified': list(self.modified_rows.values()),
            'deleted': self.deleted_rows.copy()
        }
    
    def accept_changes(self):
        """Accept all changes (like DataTable.AcceptChanges)"""
        self.modified_rows.clear()
        self.deleted_rows.clear()
        self.new_rows.clear()
        self.row_state.clear()
        self.is_dirty = False
    
    def reject_changes(self):
        """Reject all changes (like DataTable.RejectChanges)"""
        # This would require storing original values - simplified for now
        self.accept_changes()
    
    def count(self) -> int:
        """Get row count"""
        return len(self.rows)


@dataclass
class DataSet:
    """Python equivalent of ADO.NET DataSet"""
    name: str
    tables: Dict[str, DataTable] = field(default_factory=dict)
    relationships: Dict[str, Dict] = field(default_factory=dict)
    
    def add_table(self, table: DataTable):
        """Add table to dataset (like DataSet.Tables.Add)"""
        self.tables[table.name] = table
    
    def get_table(self, name: str) -> Optional[DataTable]:
        """Get table by name (like DataSet.Tables[name])"""
        return self.tables.get(name)
    
    def has_changes(self) -> bool:
        """Check if any tables have changes (like DataSet.HasChanges)"""
        return any(table.is_dirty for table in self.tables.values())
    
    def get_changes(self) -> Dict[str, Dict]:
        """Get all changes from all tables"""
        changes = {}
        for table_name, table in self.tables.items():
            if table.is_dirty:
                changes[table_name] = table.get_changes()
        return changes
    
    def accept_changes(self):
        """Accept changes in all tables (like DataSet.AcceptChanges)"""
        for table in self.tables.values():
            table.accept_changes()


class DisconnectedDataManager:
    """
    ADO.NET-style disconnected data access manager for SQL Server
    Eliminates connection pooling issues by using brief connections only
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.connection_string = self._build_connection_string()
        
        # Cache for frequently accessed datasets
        self.dataset_cache: Dict[str, DataSet] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        self.default_cache_ttl = 300  # 5 minutes
        
        self.logger.info("[DISCONNECTED] Initialized ADO.NET-style disconnected data manager")
    
    def _build_connection_string(self) -> str:
        """Build SQL Server connection string from config"""
        driver = self.config.db_driver
        server = self.config.db_server
        port = self.config.db_port if self.config.db_port != 1433 else None
        database = self.config.db_database
        username = self.config.db_username
        password = self.config.db_password
        trusted = self.config.trusted_connection
        
        # Build server string with port if not default
        server_string = f"{server},{port}" if port else server
        
        if trusted:
            connection_string = (
                f"DRIVER={{{driver}}};"
                f"SERVER={server_string};"
                f"DATABASE={database};"
                f"Trusted_Connection=yes;"
                f"Connection Timeout={self.config.connection_timeout};"
                f"Command Timeout={self.config.command_timeout};"
            )
        else:
            connection_string = (
                f"DRIVER={{{driver}}};"
                f"SERVER={server_string};"
                f"DATABASE={database};"
                f"UID={username};"
                f"PWD={password};"
                f"Connection Timeout={self.config.connection_timeout};"
                f"Command Timeout={self.config.command_timeout};"
            )
        
        # Add optional parameters
        if hasattr(self.config, 'db_encrypt') and not self.config.db_encrypt:
            connection_string += "Encrypt=no;"
        
        if hasattr(self.config, 'db_trust_server_certificate') and self.config.db_trust_server_certificate:
            connection_string += "TrustServerCertificate=yes;"
        
        return connection_string
    
    @contextmanager
    def _get_brief_connection(self):
        """Get connection for brief operations only (like C# using statement)"""
        connection = None
        start_time = time.time()
        
        try:
            self.logger.debug("[DISCONNECTED] Opening brief connection...")
            connection = pyodbc.connect(
                self.connection_string,
                timeout=30,
                autocommit=False
            )
            yield connection
            
        except Exception as e:
            self.logger.error(f"[DISCONNECTED] Connection error: {e}")
            raise
            
        finally:
            if connection:
                try:
                    connection.close()
                    elapsed = time.time() - start_time
                    self.logger.debug(f"[DISCONNECTED] Connection closed after {elapsed:.3f}s")
                except Exception as e:
                    self.logger.warning(f"[DISCONNECTED] Error closing connection: {e}")
    
    def fill_dataset(self, queries: Dict[str, str], dataset_name: str = "MainDataSet", 
                    cache_key: str = None, cache_ttl: int = None) -> DataSet:
        """
        Fill dataset with multiple tables (like C# DataAdapter.Fill)
        Similar to SqlDataAdapter.Fill(DataSet)
        """
        # Check cache first
        if cache_key and cache_key in self.dataset_cache:
            cached_time = self.cache_timestamps.get(cache_key)
            if cached_time:
                ttl = cache_ttl or self.default_cache_ttl
                if (datetime.now() - cached_time).total_seconds() < ttl:
                    self.logger.debug(f"[DISCONNECTED] Cache hit for dataset '{cache_key}'")
                    return self.dataset_cache[cache_key]
        
        dataset = DataSet(dataset_name)
        total_rows = 0
        
        # Single brief connection for all queries
        with self._get_brief_connection() as conn:
            cursor = conn.cursor()
            
            for table_name, query in queries.items():
                try:
                    start_time = time.time()
                    self.logger.debug(f"[DISCONNECTED] Executing query for table '{table_name}'")
                    
                    cursor.execute(query)
                    
                    # Get column information
                    columns = [column[0] for column in cursor.description] if cursor.description else []
                    
                    # Fetch ALL data into memory (disconnected mode)
                    rows = []
                    for row in cursor.fetchall():
                        row_dict = dict(zip(columns, row))
                        # Convert datetime objects for JSON serialization
                        for key, value in row_dict.items():
                            if isinstance(value, datetime):
                                row_dict[key] = value.isoformat()
                            elif value is None:
                                row_dict[key] = None
                        rows.append(row_dict)
                    
                    # Create DataTable with primary key detection
                    table = DataTable(
                        name=table_name,
                        columns=columns,
                        rows=rows,
                        primary_key=self._detect_primary_key(table_name)
                    )
                    
                    dataset.add_table(table)
                    total_rows += len(rows)
                    
                    elapsed = time.time() - start_time
                    self.logger.info(f"[DISCONNECTED] Filled table '{table_name}' with {len(rows)} rows in {elapsed:.2f}s")
                    
                except Exception as e:
                    self.logger.error(f"[DISCONNECTED] Error filling table '{table_name}': {e}")
                    # Create empty table on error
                    empty_table = DataTable(name=table_name, columns=[], rows=[])
                    dataset.add_table(empty_table)
        
        # Cache the dataset
        if cache_key:
            self.dataset_cache[cache_key] = dataset
            self.cache_timestamps[cache_key] = datetime.now()
        
        self.logger.info(f"[DISCONNECTED] Dataset '{dataset_name}' filled with {len(dataset.tables)} tables, {total_rows} total rows")
        return dataset
    
    def update_dataset(self, dataset: DataSet, table_configs: Dict[str, Dict] = None) -> Dict[str, bool]:
        """
        Update database with dataset changes (like C# SqlDataAdapter.Update)
        Similar to DataAdapter.Update(DataSet)
        """
        if not dataset.has_changes():
            self.logger.info("[DISCONNECTED] No changes to persist")
            return {}
        
        results = {}
        
        with self._get_brief_connection() as conn:
            cursor = conn.cursor()
            
            try:
                total_operations = 0
                
                for table_name, table in dataset.tables.items():
                    if not table.is_dirty:
                        continue
                    
                    success = True
                    operations = 0
                    
                    try:
                        self.logger.debug(f"[DISCONNECTED] Processing changes for table '{table_name}'")
                        
                        # Get table configuration
                        table_config = table_configs.get(table_name, {}) if table_configs else {}
                        
                        # Handle deletions first (like ADO.NET order)
                        for deleted_row in table.deleted_rows:
                            if table.primary_key and table.primary_key in deleted_row:
                                delete_query = self._build_delete_query(table_name, table.primary_key, table_config)
                                cursor.execute(delete_query, (deleted_row[table.primary_key],))
                                operations += 1
                        
                        # Handle new rows (inserts)
                        for new_row in table.new_rows:
                            insert_query, values = self._build_insert_query(table_name, new_row, table_config)
                            cursor.execute(insert_query, values)
                            operations += 1
                        
                        # Handle modified rows (updates)
                        for key, row in table.modified_rows.items():
                            if self._row_exists_in_db(cursor, table_name, table.primary_key, key):
                                update_query, values = self._build_update_query(table_name, row, table.primary_key, table_config)
                                cursor.execute(update_query, values)
                                operations += 1
                        
                        total_operations += operations
                        self.logger.debug(f"[DISCONNECTED] Processed {operations} operations for table '{table_name}'")
                        
                    except Exception as e:
                        self.logger.error(f"[DISCONNECTED] Error updating table '{table_name}': {e}")
                        success = False
                    
                    results[table_name] = success
                
                # Commit all changes in single transaction
                conn.commit()
                
                # Accept changes in successful tables
                for table_name, success in results.items():
                    if success:
                        dataset.get_table(table_name).accept_changes()
                
                self.logger.info(f"[DISCONNECTED] Successfully persisted {total_operations} operations across {len(results)} tables")
                
            except Exception as e:
                conn.rollback()
                self.logger.error(f"[DISCONNECTED] Error persisting changes, rolled back: {e}")
                raise
        
        return results
    
    def _detect_primary_key(self, table_name: str) -> Optional[str]:
        """Detect primary key for common tables"""
        primary_keys = {
            'job_configurations': 'job_id',
            'job_execution_history': 'execution_id',
            'database_connections': 'name',
            'job_schedules': 'schedule_id',
            'job_dependencies': 'dependency_id'
        }
        return primary_keys.get(table_name)
    
    def _row_exists_in_db(self, cursor, table_name: str, primary_key: str, key_value: Any) -> bool:
        """Check if row exists in database"""
        cursor.execute(f"SELECT 1 FROM {table_name} WHERE {primary_key} = ?", (key_value,))
        return cursor.fetchone() is not None
    
    def _build_delete_query(self, table_name: str, primary_key: str, config: Dict = None) -> str:
        """Build DELETE query"""
        # config parameter available for future extensions (e.g., soft deletes)
        return f"DELETE FROM {table_name} WHERE {primary_key} = ?"
    
    def _build_insert_query(self, table_name: str, row: Dict, config: Dict = None) -> tuple:
        """Build INSERT query"""
        # Exclude auto-generated columns
        exclude_columns = config.get('exclude_on_insert', []) if config else []
        
        # Filter out excluded columns
        filtered_row = {k: v for k, v in row.items() if k not in exclude_columns}
        
        columns = ", ".join(filtered_row.keys())
        placeholders = ", ".join(["?" for _ in filtered_row])
        values = list(filtered_row.values())
        
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        return query, values
    
    def _build_update_query(self, table_name: str, row: Dict, primary_key: str, config: Dict = None) -> tuple:
        """Build UPDATE query"""
        # Exclude primary key and auto-generated columns from updates
        exclude_columns = config.get('exclude_on_update', [primary_key]) if config else [primary_key]
        
        # Filter out excluded columns
        update_columns = {k: v for k, v in row.items() if k not in exclude_columns}
        
        set_clause = ", ".join([f"{col} = ?" for col in update_columns.keys()])
        values = list(update_columns.values()) + [row[primary_key]]
        
        query = f"UPDATE {table_name} SET {set_clause} WHERE {primary_key} = ?"
        return query, values
    
    def execute_scalar(self, query: str, params: List = None) -> Any:
        """Execute scalar query and return single value"""
        with self._get_brief_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            result = cursor.fetchone()
            return result[0] if result else None
    
    def execute_non_query(self, query: str, params: List = None) -> int:
        """Execute non-query and return affected rows"""
        with self._get_brief_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            affected_rows = cursor.rowcount
            conn.commit()
            return affected_rows
    
    def clear_cache(self, cache_key: str = None):
        """Clear dataset cache"""
        if cache_key:
            self.dataset_cache.pop(cache_key, None)
            self.cache_timestamps.pop(cache_key, None)
        else:
            self.dataset_cache.clear()
            self.cache_timestamps.clear()
        
        self.logger.info(f"[DISCONNECTED] Cache cleared {'for ' + cache_key if cache_key else 'completely'}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information for monitoring"""
        return {
            'cached_datasets': list(self.dataset_cache.keys()),
            'cache_sizes': {k: len(v.tables) for k, v in self.dataset_cache.items()},
            'cache_timestamps': {k: v.isoformat() for k, v in self.cache_timestamps.items()}
        }