import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowUpDown, BrainCircuit, CheckCircle2, Download, Eye, EyeOff, FileSearch, Lightbulb, Loader2, PlugZap, Save, Search, Settings2, ShieldCheck, Sparkles } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { dataApi, type AnalysisResult, type AnalysisTestResult } from '@/lib/api'
import { Button } from '@/components/ui/button'

type ResultTab = 'records' | 'directions' | 'batches' | 'tasks'
type RecordSort = 'default' | 'quality' | 'evidence'

interface Intelligence {
  topics: { topic: string; content_count: number; platforms: Record<string, number>; representative_terms: string[]; recent_count: number; trend: string; evidence_count: number; quality_score: number }[]
  research_directions: { research_direction: string; score: number; topic: string; why_now: string; research_questions: string[]; recommended_methods: string[]; evidence_topics: string[] }[]
}

const inputClass = 'h-10 w-full rounded-md border border-white/10 bg-[#171717] px-3 text-sm text-zinc-100 outline-none transition-colors focus:border-cyan-400/70'
const labelClass = 'block text-xs text-zinc-400'

function asArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : []
}

export function AnalysisWorkspace() {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<string[]>([])
  const [mergeFiles, setMergeFiles] = useState(true)
  const [limit, setLimit] = useState(500)
  const [message, setMessage] = useState('')
  const [selectedThemes, setSelectedThemes] = useState<string[]>([])
  const [customThemes, setCustomThemes] = useState('')
  const [resultPath, setResultPath] = useState('')
  const [meta, setMeta] = useState<AnalysisResult>()
  const [batchSummaries, setBatchSummaries] = useState<NonNullable<AnalysisResult['batch_summaries']>>([])
  const [batchResults, setBatchResults] = useState<{ path: string; status: 'completed' | 'failed'; error?: string; input_count?: number; output_count?: number }[]>([])
  const [intelligence, setIntelligence] = useState<Intelligence>()
  const [resultTab, setResultTab] = useState<ResultTab>('records')
  const [recordSearch, setRecordSearch] = useState('')
  const [recordSort, setRecordSort] = useState<RecordSort>('default')
  const [elapsed, setElapsed] = useState(0)

  const [provider, setProvider] = useState('deepseek')
  const [model, setModel] = useState('deepseek-chat')
  const [baseUrl, setBaseUrl] = useState('https://api.deepseek.com/v1')
  const [batchSize, setBatchSize] = useState(50)
  const [enrichItems, setEnrichItems] = useState(false)
  const [keyValue, setKeyValue] = useState('')
  const [keyEdited, setKeyEdited] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const [configDirty, setConfigDirty] = useState(false)
  const [configMessage, setConfigMessage] = useState('')
  const [testResult, setTestResult] = useState<AnalysisTestResult | null>(null)

  const { data: filesData } = useQuery({ queryKey: ['analysisFiles'], queryFn: async () => (await dataApi.getFiles(undefined, undefined, false)).data.files, staleTime: 5000 })
  const { data: aiConfig } = useQuery({ queryKey: ['analysisConfig'], queryFn: async () => (await dataApi.getAnalysisConfig()).data, retry: 1 })

  useEffect(() => {
    if (!aiConfig || configDirty) return
    setModel(aiConfig.model)
    setBaseUrl(aiConfig.base_url)
    setBatchSize(aiConfig.batch_size)
    setEnrichItems(aiConfig.enrich_items)
    const match = aiConfig.providers.find((item) => item.base_url === aiConfig.base_url)
    setProvider(match?.value || 'custom')
  }, [aiConfig, configDirty])

  const files = (filesData || []).filter((file) => ['jsonl', 'json', 'csv', 'xlsx', 'xls'].includes(file.type.toLowerCase()) && !file.path.split(/[\\/]/).includes('scientist'))
  const sourceKind = (path: string) => {
    const parts = path.split(/[\\/]/).map((part) => part.toLowerCase())
    if (parts.includes('papers') || parts.includes('arxiv') || parts.includes('openalex')) return 'papers'
    if (parts.includes('repositories') || parts.includes('github')) return 'repositories'
    return 'platforms'
  }
  const fileGroups = [
    { label: '论文文件', hint: 'arXiv / OpenAlex 论文；关联仓库信息随论文存放', files: files.filter((file) => sourceKind(file.path) === 'papers') },
    { label: '开源项目', hint: 'GitHub 等代码仓库', files: files.filter((file) => sourceKind(file.path) === 'repositories') },
    { label: '平台内容', hint: '社交媒体正文、评论与讨论', files: files.filter((file) => sourceKind(file.path) === 'platforms') },
  ].filter((group) => group.files.length > 0)

  const resultQuery = useQuery({ queryKey: ['analysisResult', resultPath], queryFn: async () => (await dataApi.getFileContent(resultPath, 200)).data, enabled: Boolean(resultPath) })
  const toggleTheme = (theme: string) => setSelectedThemes((current) => current.includes(theme) ? current.filter((item) => item !== theme) : [...current, theme])
  const parsedCustomThemes = customThemes.split(/[，,\n]/).map((item) => item.trim()).filter(Boolean)
  const hasScope = selectedThemes.length > 0 || parsedCustomThemes.length > 0
  const toggleFile = (path: string) => setSelected((current) => current.includes(path) ? current.filter((item) => item !== path) : [...current, path])

  const analyzeMutation = useMutation({
    mutationFn: () => dataApi.analyzeMany(selected, selectedThemes, parsedCustomThemes, limit, mergeFiles),
    onMutate: () => { setElapsed(0); setMessage('') },
    onSuccess: (response) => {
      const completed = response.data.results.filter((item) => item.status === 'completed' && item.result)
      const first = completed[0]?.result
      if (first) {
        setResultPath(first.output_file)
        setMeta(first)
        setBatchSummaries(first.batch_summaries || [])
        setIntelligence(first.intelligence as Intelligence | undefined)
        setResultTab('records')
      }
      setBatchResults(response.data.results.map((item) => ({ path: item.path, status: item.status, error: item.error, input_count: item.result?.input_count, output_count: item.result?.output_count })))
      setMessage(`${mergeFiles ? '合并分析' : '批量分析'}完成：${response.data.completed} 个成功，${response.data.failed} 个失败。`)
      void queryClient.invalidateQueries({ queryKey: ['analysisFiles'] })
    },
    onError: (error: Error) => setMessage(`分析失败：${error.message}`),
  })

  useEffect(() => {
    if (!analyzeMutation.isPending) return
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [analyzeMutation.isPending])

  const saveConfigMutation = useMutation({
    mutationFn: () => dataApi.setAnalysisConfig({
      model: model.trim(),
      base_url: baseUrl.trim(),
      batch_size: batchSize,
      enrich_items: enrichItems,
      ...(keyEdited ? { api_key: keyValue } : {}),
    }),
    onSuccess: () => {
      setConfigDirty(false)
      setKeyEdited(false)
      setKeyValue('')
      setConfigMessage('配置已保存')
      setTestResult(null)
      toast.success('分析 API 配置已保存')
      void queryClient.invalidateQueries({ queryKey: ['analysisConfig'] })
    },
    onError: (error: Error) => { setConfigMessage(`保存失败：${error.message}`); toast.error(`保存失败：${error.message}`) },
  })

  const testConfigMutation = useMutation({
    mutationFn: () => dataApi.testAnalysisConfig({ model: model.trim(), base_url: baseUrl.trim(), ...(keyEdited ? { api_key: keyValue } : {}) }),
    onSuccess: (response) => {
      setTestResult(response.data)
      if (response.data.ok) toast.success(`连接成功，延迟 ${response.data.latency_ms} ms`)
      else toast.error(response.data.error || '连接失败')
    },
    onError: (error: Error) => { setTestResult({ ok: false, error: error.message }); toast.error(error.message) },
  })

  const applyProvider = (value: string) => {
    setProvider(value)
    const preset = aiConfig?.providers.find((item) => item.value === value)
    if (preset && preset.value !== 'custom') {
      setBaseUrl(preset.base_url)
      if (preset.models.length) setModel(preset.models[0])
    }
    setConfigDirty(true)
    setTestResult(null)
  }

  const modelOptions = useMemo(() => {
    const preset = aiConfig?.providers.find((item) => item.value === provider)
    const values = [...(preset?.models || []), ...(aiConfig?.models || []).map((item) => item.value)]
    return Array.from(new Set(values))
  }, [aiConfig, provider])

  const records = useMemo(() => {
    const rows = (resultQuery.data?.data || []) as Record<string, unknown>[]
    const keyword = recordSearch.trim().toLowerCase()
    const filtered = keyword ? rows.filter((row) => `${row.title || ''} ${row.summary || ''} ${asArray(row.topics).join(' ')}`.toLowerCase().includes(keyword)) : rows
    if (recordSort === 'quality') return [...filtered].sort((a, b) => Number(b.quality_score || 0) - Number(a.quality_score || 0))
    if (recordSort === 'evidence') return [...filtered].sort((a, b) => asArray(b.evidence).length - asArray(a.evidence).length)
    return filtered
  }, [resultQuery.data, recordSearch, recordSort])

  const batchErrors = meta?.batch_errors || []

  return <div className="max-w-5xl mx-auto space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3"><BrainCircuit className="w-6 h-6 text-cyan-300" /><div><h1 className="text-xl font-semibold">内容分析</h1><p className="mt-1 text-xs text-zinc-500">规则分析打底，AI 批次总结与可选逐条增强；结果带来源与证据入库。</p></div></div>
      <span className={`rounded-full border px-3 py-1 text-xs ${aiConfig?.ai_enabled ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300' : 'border-amber-400/40 bg-amber-400/10 text-amber-300'}`}>{aiConfig?.ai_enabled ? 'AI 已配置' : '未配置 API Key'}</span>
    </div>

    <section className="rounded-xl border border-white/[0.08] bg-[#202020] p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2"><Settings2 className="w-5 h-5 text-cyan-300" /><div><h2 className="font-medium">模型与接口配置</h2><p className="mt-1 text-xs text-zinc-500">配置 OpenAI 兼容接口；密钥只保存在本地 .env，界面仅显示掩码。</p></div></div>
        {aiConfig?.api_key_set && <span className="text-xs text-zinc-500">当前密钥 {aiConfig.api_key_masked}</span>}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {(aiConfig?.providers || []).map((preset) => <button key={preset.value} type="button" onClick={() => applyProvider(preset.value)} className={`rounded-md border px-3 py-1.5 text-xs transition-colors ${provider === preset.value ? 'border-cyan-400/70 bg-cyan-400/10 text-cyan-200' : 'border-white/10 bg-[#171717] text-zinc-400 hover:border-cyan-400/50 hover:text-zinc-200'}`}>{preset.label}</button>)}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <label className={labelClass}>接口地址<input value={baseUrl} onChange={(event) => { setBaseUrl(event.target.value); setConfigDirty(true); setTestResult(null) }} placeholder="https://api.deepseek.com/v1" className={`mt-2 ${inputClass}`} /></label>
        <label className={labelClass}>模型<input value={model} onChange={(event) => { setModel(event.target.value); setConfigDirty(true); setTestResult(null) }} list="analysis-model-options" placeholder="deepseek-chat" className={`mt-2 ${inputClass}`} /><datalist id="analysis-model-options">{modelOptions.map((value) => <option key={value} value={value} />)}</datalist></label>
        <label className={labelClass}>API Key<div className="relative mt-2"><input type={showKey ? 'text' : 'password'} value={keyValue} onChange={(event) => { setKeyValue(event.target.value); setKeyEdited(true); setConfigDirty(true); setTestResult(null) }} placeholder={aiConfig?.api_key_masked || '粘贴密钥，留空表示不修改'} autoComplete="off" className={`${inputClass} pr-10`} /><button type="button" onClick={() => setShowKey((value) => !value)} className="absolute right-2 top-2.5 text-zinc-500 hover:text-zinc-200" title={showKey ? '隐藏' : '显示'}>{showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button></div></label>
        <div className="grid grid-cols-2 gap-3">
          <label className={labelClass}>批次大小<input type="number" min={10} max={100} value={batchSize} onChange={(event) => { setBatchSize(Math.max(10, Math.min(100, Number(event.target.value) || 50))); setConfigDirty(true) }} className={`mt-2 ${inputClass}`} /></label>
          <label className={`${labelClass} flex flex-col justify-end`}><span className="mb-2">逐条 AI 增强</span><span className="flex h-10 items-center gap-2 rounded-md border border-white/10 bg-[#171717] px-3"><input type="checkbox" checked={enrichItems} onChange={(event) => { setEnrichItems(event.target.checked); setConfigDirty(true) }} className="h-4 w-4 accent-cyan-400" /><span className="text-xs text-zinc-400">质量分最高的前 100 条</span></span></label>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => testConfigMutation.mutate()} disabled={testConfigMutation.isPending} className="border border-white/10 text-zinc-300 hover:text-cyan-200">{testConfigMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlugZap className="w-4 h-4" />}测试连接</Button>
        <Button size="sm" onClick={() => saveConfigMutation.mutate()} disabled={!configDirty || saveConfigMutation.isPending} className="bg-cyan-400 text-slate-950 hover:bg-cyan-300">{saveConfigMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}保存配置</Button>
        {testResult && <span className={`flex items-center gap-1.5 text-xs ${testResult.ok ? 'text-emerald-300' : 'text-rose-300'}`}>{testResult.ok ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}{testResult.ok ? `连接成功 · ${testResult.latency_ms} ms · ${testResult.model}` : testResult.error}</span>}
        {configMessage && !testResult && <span className="text-xs text-zinc-400">{configMessage}</span>}
      </div>
    </section>

    <section className="rounded-xl border border-white/[0.08] bg-[#202020] p-5">
      <div className="flex items-start gap-3 mb-4"><FileSearch className="w-5 h-5 text-violet-300 mt-0.5" /><div><h2 className="font-medium">选择采集文件</h2><p className="text-xs text-zinc-500 mt-1">按论文、开源项目和平台内容分组；已排除分析结果与生成的 Idea。</p></div></div>
      <div className="rounded-lg border border-white/[0.08] bg-[#171717] overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-white/[0.08] px-3 py-2"><span className="text-xs text-zinc-400">已选 {selected.length} / {files.length} 个文件</span><div className="flex gap-3"><button type="button" onClick={() => setSelected(files.map((file) => file.path))} className="text-xs text-cyan-300 hover:text-cyan-200">全选</button><button type="button" onClick={() => setSelected([])} className="text-xs text-zinc-400 hover:text-zinc-200">清空</button></div></div>
        <div className="max-h-64 overflow-auto">
          {fileGroups.map((group) => <div key={group.label} className="border-b border-white/[0.06] last:border-b-0"><div className="bg-white/[0.03] px-3 py-2"><p className="text-xs font-medium text-zinc-300">{group.label}<span className="ml-2 font-normal text-zinc-500">{group.files.length} 个</span></p><p className="mt-0.5 text-[11px] text-zinc-500">{group.hint}</p></div>{group.files.map((file) => <label key={file.path} className="flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-white/[0.03]"><input type="checkbox" checked={selected.includes(file.path)} onChange={() => toggleFile(file.path)} className="h-4 w-4 accent-cyan-400" /><span className="min-w-0 flex-1 truncate text-sm text-zinc-200">{file.path}</span><span className="shrink-0 text-xs text-zinc-500">{file.record_count ?? '-'} 条</span></label>)}</div>)}
          {files.length === 0 && <p className="px-3 py-6 text-center text-sm text-zinc-500">暂无可分析的原始采集文件，请先在新任务页采集。</p>}
        </div>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <label className={labelClass}>每文件读取上限<input type="number" min={1} max={5000} value={limit} onChange={(event) => setLimit(Math.max(1, Math.min(5000, Number(event.target.value) || 500)))} className={`mt-2 ${inputClass}`} /></label>
        <label className={`${labelClass} flex items-end gap-2 pb-2`}><input type="checkbox" checked={mergeFiles} onChange={(event) => setMergeFiles(event.target.checked)} className="h-4 w-4 accent-cyan-400" />合并为一个结果文件</label>
      </div>
      <div className="mt-5 border-t border-white/[0.08] pt-5">
        <div className="flex items-start justify-between gap-3"><div><h2 className="font-medium">分析范围</h2><p className="mt-1 text-xs text-zinc-500">范围外内容不会进入热点、候选方向、知识库同步或后续研究想法。</p></div><button type="button" onClick={() => setSelectedThemes(aiConfig?.themes || [])} className="shrink-0 text-xs text-cyan-300 hover:text-cyan-200">全选固定主题</button></div>
        <div className="mt-3 flex flex-wrap gap-2">{(aiConfig?.themes || []).map((theme) => <button key={theme} type="button" onClick={() => toggleTheme(theme)} className={`rounded-md border px-2.5 py-1.5 text-xs transition-colors ${selectedThemes.includes(theme) ? 'border-cyan-400/70 bg-cyan-400/10 text-cyan-200' : 'border-white/10 bg-[#171717] text-zinc-400 hover:border-cyan-400/50 hover:text-zinc-200'}`}>{theme}</button>)}</div>
        <label className={`mt-4 ${labelClass}`}>自定义主题<input value={customThemes} onChange={(event) => setCustomThemes(event.target.value)} placeholder="例如：医疗 AI 安全，多模态模型越狱（用逗号分隔）" className={`mt-2 ${inputClass}`} /></label>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button onClick={() => analyzeMutation.mutate()} disabled={selected.length === 0 || !hasScope || analyzeMutation.isPending} className="bg-cyan-400 text-slate-950 hover:bg-cyan-300">{analyzeMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}{analyzeMutation.isPending ? `正在分析 ${elapsed}s` : mergeFiles ? `合并分析 ${selected.length} 个文件` : `分别分析 ${selected.length} 个文件`}</Button>
        {!hasScope && <p className="text-xs text-amber-300">请至少选择一个主题或填写自定义主题</p>}
        {message && <p className="text-sm text-zinc-400 flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />{message}</p>}
      </div>
    </section>

    {meta && <section className="grid grid-cols-2 gap-2 md:grid-cols-6">
      {[
        ['输入', meta.input_count],
        ['输出', meta.output_count],
        ['范围外', meta.scope_excluded ?? 0],
        ['耗时', `${((meta.duration_ms || 0) / 1000).toFixed(1)}s`],
        ['AI 增强', meta.ai_enriched_count ?? 0],
        ['批次失败', batchErrors.length],
      ].map(([label, value]) => <div key={String(label)} className="rounded-lg border border-white/[0.07] bg-[#1d1d1d] p-3"><p className="text-[11px] text-zinc-500">{label}</p><p className={`mt-1 text-lg font-semibold ${label === '批次失败' && Number(value) > 0 ? 'text-rose-300' : 'text-zinc-100'}`}>{value}</p></div>)}
    </section>}

    {batchResults.length > 0 && <section className="rounded-xl border border-white/[0.08] bg-[#202020] p-4">
      <div className="flex flex-wrap gap-2">
        {([['records', '记录'], ['directions', '研究方向'], ['batches', '批次摘要'], ['tasks', '任务结果']] as [ResultTab, string][]).map(([value, label]) => <button key={value} type="button" onClick={() => setResultTab(value)} className={`rounded-md border px-3 py-1.5 text-xs ${resultTab === value ? 'border-cyan-400/70 bg-cyan-400/10 text-cyan-200' : 'border-white/10 bg-[#171717] text-zinc-400 hover:text-zinc-200'}`}>{label}</button>)}
        {resultPath && <a href={dataApi.getDownloadUrl(resultPath)} className="ml-auto flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200"><Download className="w-3.5 h-3.5" />下载完整结果</a>}
      </div>

      {resultTab === 'records' && <div className="mt-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative"><Search className="absolute left-2.5 top-2.5 w-4 h-4 text-zinc-500" /><input value={recordSearch} onChange={(event) => setRecordSearch(event.target.value)} placeholder="搜索标题、摘要或主题" className="h-9 w-64 rounded-md border border-white/10 bg-[#171717] pl-8 pr-3 text-sm text-zinc-100 outline-none focus:border-cyan-400/60" /></div>
          <div className="relative"><ArrowUpDown className="absolute left-2.5 top-2.5 w-4 h-4 text-zinc-500" /><select value={recordSort} onChange={(event) => setRecordSort(event.target.value as RecordSort)} className="h-9 rounded-md border border-white/10 bg-[#171717] pl-8 pr-3 text-sm text-zinc-200 outline-none focus:border-cyan-400/60"><option value="default">默认顺序</option><option value="quality">质量分降序</option><option value="evidence">证据数降序</option></select></div>
          <span className="text-xs text-zinc-500">{records.length} 条</span>
        </div>
        <div className="mt-3 space-y-3 max-h-[560px] overflow-auto">
          {resultQuery.isLoading && <p className="text-sm text-zinc-500">正在加载结果…</p>}
          {records.map((item, index) => <article key={index} className="rounded-lg border border-white/[0.07] bg-[#171717] p-4">
            <div className="flex items-start justify-between gap-4">
              <h3 className="text-sm font-medium text-zinc-100">{String(item.title || `记录 ${index + 1}`)}</h3>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-[11px] text-zinc-500">质量 {Number(item.quality_score || 0).toFixed(2)}</span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] ${item.analysis_method === 'ai' ? 'bg-violet-400/10 text-violet-300' : 'bg-cyan-400/10 text-cyan-300'}`}>{item.analysis_method === 'ai' ? 'AI' : '规则'}</span>
              </div>
            </div>
            {Boolean(item.summary) && <p className="mt-2 text-sm leading-6 text-zinc-300">{String(item.summary)}</p>}
            <div className="mt-3 flex flex-wrap gap-2">{asArray(item.topics).slice(0, 6).map((topic) => <span key={topic} className="rounded-full bg-cyan-400/10 px-2 py-1 text-[11px] text-cyan-200">{topic}</span>)}</div>
            {asArray(item.claims).length > 0 && <div className="mt-3 border-t border-white/[0.06] pt-3"><p className="text-[11px] text-violet-200">观点</p>{asArray(item.claims).slice(0, 3).map((claim) => <p key={claim} className="mt-1 text-xs leading-5 text-zinc-400">· {claim}</p>)}</div>}
            {asArray(item.evidence).length > 0 && <div className="mt-3 border-t border-white/[0.06] pt-3"><p className="text-[11px] text-amber-200">证据句</p>{asArray(item.evidence).slice(0, 2).map((evidence) => <p key={evidence} className="mt-1 text-xs leading-5 text-zinc-400">“{evidence}”</p>)}</div>}
            {Boolean(item.source_url) && <a href={String(item.source_url)} target="_blank" rel="noreferrer" className="mt-3 inline-block text-[11px] text-cyan-300 hover:text-cyan-200">原始来源</a>}
          </article>)}
          {!resultQuery.isLoading && records.length === 0 && <p className="py-6 text-center text-sm text-zinc-500">没有匹配的记录。</p>}
        </div>
      </div>}

      {resultTab === 'directions' && intelligence && <div className="mt-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{intelligence.research_directions.slice(0, 6).map((direction) => <article key={direction.research_direction} className="rounded-xl border border-emerald-400/20 bg-[#171717] p-4"><div className="flex items-start justify-between gap-3"><div className="flex items-center gap-2"><Lightbulb className="w-4 h-4 text-amber-300" /><h3 className="text-sm font-medium">{direction.research_direction}</h3></div><span className="text-xs font-semibold text-emerald-300">{direction.score}/100</span></div><p className="mt-3 text-xs leading-5 text-zinc-300">{direction.why_now}</p><div className="mt-3 space-y-1">{direction.research_questions.map((question) => <p key={question} className="text-xs text-zinc-400">研究问题：{question}</p>)}</div><div className="mt-3 flex flex-wrap gap-1.5">{direction.recommended_methods.map((method) => <span key={method} className="rounded-full bg-emerald-400/10 px-2 py-1 text-[11px] text-emerald-200">{method}</span>)}</div></article>)}</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">{intelligence.topics.slice(0, 6).map((topic) => <article key={topic.topic} className="rounded-lg border border-white/[0.07] bg-[#1d1d1d] p-4"><div className="flex items-center justify-between gap-2"><div className="flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-cyan-300" /><h3 className="text-sm font-medium">{topic.topic}</h3></div><span className={`text-[11px] ${topic.trend === 'rising' ? 'text-emerald-300' : 'text-zinc-400'}`}>{topic.trend === 'rising' ? '升温' : '稳定'}</span></div><p className="mt-2 text-xs text-zinc-500">{topic.content_count} 条内容 · {Object.keys(topic.platforms).length} 个平台 · 证据 {topic.evidence_count} 条</p><div className="mt-2 flex flex-wrap gap-1.5">{topic.representative_terms.slice(0, 4).map((term) => <span key={term} className="text-[10px] text-cyan-200">#{term}</span>)}</div></article>)}</div>
      </div>}

      {resultTab === 'batches' && <div className="mt-4 space-y-3">
        {batchErrors.length > 0 && <div className="rounded-lg border border-rose-400/30 bg-rose-400/10 p-3 text-xs text-rose-200"><p className="flex items-center gap-1.5 font-medium"><AlertTriangle className="w-4 h-4" />{batchErrors.length} 个批次总结失败，已回退到规则分析。</p>{batchErrors.map((item) => <p key={item.batch} className="mt-1 text-rose-300/80">第 {item.batch} 批：{item.error}</p>)}</div>}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{batchSummaries.map((batch) => <article key={batch.batch} className="rounded-lg border border-white/[0.07] bg-[#171717] p-4"><div className="flex items-center justify-between"><h3 className="text-sm font-medium">第 {batch.batch} 批</h3><span className="text-[11px] text-violet-300">{batch.record_count} 条</span></div>{batch.summary && <p className="mt-2 text-sm leading-6 text-zinc-300">{batch.summary}</p>}<div className="mt-3 flex flex-wrap gap-2">{(batch.topics || []).map((topic) => <span key={topic} className="rounded-full bg-violet-400/10 px-2 py-1 text-[11px] text-violet-200">{topic}</span>)}</div>{(batch.claims || []).length > 0 && <div className="mt-3 border-t border-white/[0.06] pt-2">{(batch.claims || []).map((claim) => <p key={claim} className="mt-1 text-xs text-zinc-400">· {claim}</p>)}</div>}</article>)}</div>
        {batchSummaries.length === 0 && batchErrors.length === 0 && <p className="py-6 text-center text-sm text-zinc-500">本次未生成 AI 批次摘要（未配置密钥或无匹配记录）。</p>}
      </div>}

      {resultTab === 'tasks' && <div className="mt-3 space-y-2">{batchResults.map((item) => <div key={item.path} className="flex items-center justify-between gap-3 rounded border border-white/[0.07] bg-[#171717] px-3 py-2 text-xs"><span className="truncate text-zinc-300">{item.path}</span><span className={item.status === 'completed' ? 'shrink-0 text-emerald-300' : 'shrink-0 text-rose-300'}>{item.status === 'completed' ? `完成 · ${item.input_count}→${item.output_count} 条` : `失败 · ${item.error || '未知错误'}`}</span></div>)}</div>}
    </section>}

    <section className="grid grid-cols-1 md:grid-cols-3 gap-3">{[['清洗去重', '移除空内容、规范字段、合并重复记录'], ['结构化分析', '摘要、关键词、主题、证据和来源信息'], ['AI 增强（可选）', '批次总结默认开启；逐条增强可在配置中打开']].map(([title, desc]) => <div key={title} className="rounded-lg border border-white/[0.07] bg-[#1d1d1d] p-4"><h3 className="text-sm font-medium">{title}</h3><p className="mt-2 text-xs leading-5 text-zinc-500">{desc}</p></div>)}</section>
  </div>
}
