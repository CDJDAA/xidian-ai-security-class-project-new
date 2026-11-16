import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, Download, FileJson, Loader2, RefreshCw, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { dataApi, type DataFile } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { formatDateTime, formatFileSize } from '@/lib/utils'

interface DataStats {
  total_files: number
  total_size: number
  namespace?: string
  kb_root?: string
  by_platform: Record<string, number>
  by_type: Record<string, number>
  by_category?: Record<string, number>
}

function recordTitle(record: Record<string, unknown>, index: number) {
  return String(record.title || record.name || record.note_title || `记录 ${index + 1}`)
}

function recordSummary(record: Record<string, unknown>) {
  return String(record.summary || record.desc || record.content || record.text || '')
}

export function DataExplorer({ compact = false }: { compact?: boolean }) {
  const queryClient = useQueryClient()
  const [platform, setPlatform] = useState('')
  const [fileType, setFileType] = useState('')
  const [selectedPath, setSelectedPath] = useState('')

  const filesQuery = useQuery({
    queryKey: ['dataFiles', platform, fileType],
    queryFn: async () => (await dataApi.getFiles(platform || undefined, fileType || undefined, true)).data.files,
    staleTime: 5000,
  })
  const statsQuery = useQuery({
    queryKey: ['dataStats'],
    queryFn: async () => (await dataApi.getStats()).data as DataStats,
    staleTime: 10000,
  })
  const previewQuery = useQuery({
    queryKey: ['dataPreview', selectedPath],
    queryFn: async () => (await dataApi.getFileContent(selectedPath, 50)).data,
    enabled: Boolean(selectedPath),
  })
  const deleteMutation = useMutation({
    mutationFn: (path: string) => dataApi.deleteFile(path),
    onSuccess: (_, path) => {
      toast.success(`已删除 ${path}`)
      if (path === selectedPath) setSelectedPath('')
      void queryClient.invalidateQueries({ queryKey: ['dataFiles'] })
      void queryClient.invalidateQueries({ queryKey: ['dataStats'] })
    },
    onError: (error: Error) => toast.error(`删除失败：${error.message}`),
  })

  const files = filesQuery.data || []
  const stats = statsQuery.data
  const selected = useMemo(() => files.find((file) => file.path === selectedPath), [files, selectedPath])
  const platforms = Object.keys(stats?.by_platform || {}).sort()
  const types = Object.keys(stats?.by_type || {}).sort()

  const removeFile = (file: DataFile) => {
    if (window.confirm(`确定删除 ${file.path}？该操作不可撤销。`)) deleteMutation.mutate(file.path)
  }

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-white/[0.08] bg-[#202020] p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <Database className="w-5 h-5 text-cyan-300" />
            <div>
              <h2 className="font-medium">采集结果</h2>
              <p className="mt-1 text-xs text-zinc-500">命名空间 {stats?.namespace || '—'}；论文 {stats?.by_category?.papers ?? 0} · 开源项目 {stats?.by_category?.repositories ?? 0} · 平台内容 {stats?.by_category?.platforms ?? 0}。删除只影响本地 data 目录。</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => { void filesQuery.refetch(); void statsQuery.refetch() }} className="text-zinc-400 hover:text-cyan-200">
            <RefreshCw className={`w-4 h-4 ${filesQuery.isFetching ? 'animate-spin' : ''}`} />刷新
          </Button>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
          <div className="rounded-lg border border-white/[0.07] bg-[#171717] p-3"><p className="text-[11px] text-zinc-500">文件总数</p><p className="mt-1 text-lg font-semibold text-zinc-100">{stats?.total_files ?? '—'}</p></div>
          <div className="rounded-lg border border-white/[0.07] bg-[#171717] p-3"><p className="text-[11px] text-zinc-500">占用空间</p><p className="mt-1 text-lg font-semibold text-zinc-100">{stats ? formatFileSize(stats.total_size) : '—'}</p></div>
          <div className="rounded-lg border border-white/[0.07] bg-[#171717] p-3"><p className="text-[11px] text-zinc-500">平台</p><p className="mt-1 text-lg font-semibold text-zinc-100">{platforms.length}</p></div>
          <div className="rounded-lg border border-white/[0.07] bg-[#171717] p-3"><p className="text-[11px] text-zinc-500">格式</p><p className="mt-1 text-lg font-semibold text-zinc-100">{types.length}</p></div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <select value={platform} onChange={(event) => setPlatform(event.target.value)} className="h-9 rounded-md border border-white/10 bg-[#171717] px-3 text-sm text-zinc-200 outline-none focus:border-cyan-400/60">
            <option value="">全部平台</option>
            {platforms.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <select value={fileType} onChange={(event) => setFileType(event.target.value)} className="h-9 rounded-md border border-white/10 bg-[#171717] px-3 text-sm text-zinc-200 outline-none focus:border-cyan-400/60">
            <option value="">全部格式</option>
            {types.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <section className="rounded-xl border border-white/[0.08] bg-[#202020] p-4">
          <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-medium">文件列表</h3><span className="text-xs text-zinc-500">{files.length} 个</span></div>
          <div className={`space-y-2 overflow-auto ${compact ? 'max-h-[300px]' : 'max-h-[560px]'}`}>
            {filesQuery.isLoading && <p className="py-6 text-center text-sm text-zinc-500">正在加载…</p>}
            {!filesQuery.isLoading && files.length === 0 && <p className="py-6 text-center text-sm text-zinc-500">暂无采集结果。</p>}
            {files.map((file) => (
              <button key={file.path} type="button" onClick={() => setSelectedPath(file.path)} className={`w-full rounded-lg border p-3 text-left transition-colors ${selectedPath === file.path ? 'border-cyan-400/70 bg-cyan-400/10' : 'border-white/[0.07] bg-[#171717] hover:border-cyan-400/40'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-zinc-100">{file.path}</p>
                    <p className="mt-1 text-[11px] text-zinc-500">{file.type.toUpperCase()} · {file.record_count ?? '—'} 条 · {formatFileSize(file.size)} · {formatDateTime(file.modified_at)}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <a href={dataApi.getDownloadUrl(file.path)} onClick={(event) => event.stopPropagation()} className="rounded p-1.5 text-zinc-400 hover:bg-white/10 hover:text-cyan-200" title="下载"><Download className="w-4 h-4" /></a>
                    <button type="button" onClick={(event) => { event.stopPropagation(); removeFile(file) }} className="rounded p-1.5 text-zinc-400 hover:bg-rose-400/10 hover:text-rose-300" title="删除"><Trash2 className="w-4 h-4" /></button>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-white/[0.08] bg-[#202020] p-4">
          <div className="mb-3 flex items-center justify-between gap-3"><h3 className="text-sm font-medium">内容预览</h3>{selected && <span className="truncate text-xs text-zinc-500">{selected.name}</span>}</div>
          {!selected && <div className="flex min-h-[200px] flex-col items-center justify-center gap-2 text-zinc-500"><FileJson className="w-8 h-8" /><p className="text-sm">从左侧选择文件查看预览。</p></div>}
          {selected && previewQuery.isLoading && <p className="py-8 text-center text-sm text-zinc-500"><Loader2 className="mx-auto mb-2 w-4 h-4 animate-spin" />正在读取预览…</p>}
          {selected && previewQuery.isError && <p className="py-8 text-center text-sm text-rose-300">读取失败：{previewQuery.error.message}</p>}
          {selected && previewQuery.data && (
            <div>
              <p className="mb-3 text-xs text-zinc-500">共 {previewQuery.data.total} 条，当前显示前 {previewQuery.data.data.length} 条。</p>
              <div className={`space-y-2 overflow-auto ${compact ? 'max-h-[300px]' : 'max-h-[560px]'}`}>
                {previewQuery.data.data.map((record, index) => {
                  const url = String(record.source_url || record.url || '')
                  return <article key={index} className="rounded-lg border border-white/[0.07] bg-[#171717] p-3">
                    <div className="flex items-start justify-between gap-3"><h4 className="text-sm font-medium text-zinc-100">{recordTitle(record, index)}</h4>{url && <a href={url} target="_blank" rel="noreferrer" className="shrink-0 text-[11px] text-cyan-300 hover:text-cyan-200">来源</a>}</div>
                    {recordSummary(record) && <p className="mt-2 line-clamp-4 text-xs leading-5 text-zinc-400">{recordSummary(record)}</p>}
                    <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-zinc-500">
                      {Boolean(record.author || record.nickname) && <span>{String(record.author || record.nickname)}</span>}
                      {Boolean(record.published_at || record.create_time) && <span>{String(record.published_at || record.create_time)}</span>}
                      {Boolean(record.source_platform) && <span>{String(record.source_platform)}</span>}
                    </div>
                  </article>
                })}
                {previewQuery.data.data.length === 0 && <p className="py-6 text-center text-sm text-zinc-500">文件为空。</p>}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
