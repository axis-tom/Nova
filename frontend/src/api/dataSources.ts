import client from './client';
import type { DataSource, DataSourceType } from '@/types';

/**
 * 获取所有数据源
 */
export function getDataSources(): Promise<{ sources: DataSource[] }> {
  return client.get('/data-sources');
}

/**
 * 获取单个数据源详情
 * @param id - 数据源ID
 */
export function getDataSource(id: string | number): Promise<{ source: DataSource }> {
  return client.get(`/data-sources/${id}`);
}

/**
 * 创建数据源
 * @param data - { name, type, config, ... }
 */
export function createDataSource(data: Partial<DataSource>): Promise<{ source: DataSource }> {
  return client.post('/data-sources', data);
}

/**
 * 更新数据源
 * @param id - 数据源ID
 * @param data - 更新数据
 */
export function updateDataSource(id: string | number, data: Partial<DataSource>): Promise<{ source: DataSource }> {
  return client.put(`/data-sources/${id}`, data);
}

/**
 * 删除数据源
 * @param id - 数据源ID
 */
export function deleteDataSource(id: string | number): Promise<unknown> {
  return client.delete(`/data-sources/${id}`);
}

/**
 * 测试数据源连接
 * @param config - 数据源配置
 */
export function testDataSource(config: Record<string, unknown>): Promise<{ success: boolean; message: string }> {
  return client.post('/data-sources/test', config);
}

export function getDataSourceTypes(): Promise<Record<string, DataSourceType>> {
  return client.get('/data-sources/types');
}
