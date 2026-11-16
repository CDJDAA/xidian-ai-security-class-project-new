import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, FolderSync, Loader2, RefreshCw, Save, Search } from 'lucide-react'
import { toast } from 'sonner'
import { scientistApi, type ObsidianVault } from '@/lib/api'
import { Button } from '@/components/ui/button'

function vaultByKind(vaults: ObsidianVault[] | undefined, kind: ObsidianVault['kind']) {
  return vaults?.find((vault) => vault.kind === kind)
}

export function KnowledgeBaseWorkspace() {
  const queryClient = useQueryClient()
  const [kind, setKind] = useState<ObsidianVault['kind']>('academic')
  const [academicPath, setAcademicPath] = useState('')
  const [socialPath, setSocialPath] = useState('')
  const [selectedNote, setSelectedNote] = useState('')
  const [search, setSearch] = useState('')

  const vaultsQuery = useQuery({
    queryKey: ['vaultsStatus'],
    queryFn: async () => (await scientistApi.vaultsStatus()).data,
    staleTime: 10000,
  })
  const vaults = vaultsQuery.data?.vaults
  const activeVault = vaultByKind(vaults, kind)

  useEffect(() => {
    const academic = vaultByKind(vaults, 'academic')
    const social = vaultByKind(vaults, 'social')
    setAcademicPath((current) => current || academic?.path || '')
    setSocialPath((current) => current || social?.path || '')
  }, [vaults])

  useEffect(() => {
    setSelectedNote('')
  }, [kind])

  const notesQuery = useQuery({
    queryKey: ['vaultNotes', kind],
    queryFn: async () => (await scientistApi.vaultNotesByKind(kind, 5000)).data.notes,
    enabled: Boolean(activeVault?.available),
    staleTime: 5000,
  })
  const noteQuery = useQuery({
    queryKey: ['vaultNote', kind, selectedNote],
    queryFn: async () => (await scientistApi.vaultNoteByKind(kind, selectedNote)).data,
    enabled: Boolean(activeVault?.available && selectedNote),
  })

  const saveMutation = useMutation({
    mutationFn: () => scientistApi.configureVaults(academicPath.trim(), socialPath.trim()),
    onSuccess: () => {
      toast.success('知识库路径已保存')
      void queryClient.invalidateQueries({ queryKey: ['vaultsStatus'] })
      void queryClient.invalidateQueries({ queryKey: ['vaultNotes'] })
    },
    onError: (error: Error) => toast.error(`保存失败：${error.message}`),
  })
  const syncMutation = useMutation({
    mutationFn: () => scientistApi.syncVaults(),
    onSuccess: () => {
      toast.success('知识库同步完成')
      void queryClient.invalidateQueries({ queryKey: ['vaultsStatus'] })
      void queryClient.invalidateQueries({ queryKey: ['vaultNotes'] })
    },
    onError: (error: Error) => toast.error(`同步失败：${error.message}`),
  })

  const notes = useMemo(() => {
    const rows = notesQuery.data || []
    const keyword = search.trim().toLowerCase()
    if (!keyword) return rows
    return rows.filter((note) => `${note.title} ${note.path}`.toLowerCase().includes(keyword))
  }, [notesQuery.data, search])

  return <div className="max-w-6xl mx-auto space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-center gap-3"><BookOpen className="w-6 h-6 text-cyan-300" /><div><h1 className="text-xl font-semibold">知识库</h1><p className="mt-1 text-xs text-zinc-500">学术文献与社交情报分别归档为 Obsidian Markdown；数据库仍是可追溯源。</p></div></div>
      <div className="flex gap-2">
        <Button variant="ghost" size="sm" onClick={() => { void vaultsQuery.refetch(); void notesQuery.refetch() }} className="text-zinc-400 hover:text-cyan-200"><RefreshCw className={`w-4 h-4 ${vaultsQuery.isFetching || notesQuery.isFetching ? 'animate-spin' : ''}`} />刷新</Button>
        <Button size="sm" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending} className="bg-cyan-400 text-slate-950 hover:bg-cyan-300">{syncMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <FolderSync className="w-4 h-4" />}同步知识库</Button>
      </div>
    </div>

    <section className="rounded-xl border border-white/[0.08] bg-[#202020] p-5">
      <h2 className="font-medium">库路径</h2>
      <p className="mt-1 text-xs text-zinc-500">路径必须是已存在的目录；学术库建议包含 <code className="text-cyan-200">30-来源/自动采集</code>。</p>
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <label className="text-xs text-zinc-400">学术知识库<input value={academicPath} onChange={(event) => setAcademicPath(event.target.value)} placeholder="D:\\knowledge\\academic" className="mt-2 h-10 w-full rounded-md border border-white/10 bg-[#171717] px-3 text-sm text-zinc-100 outline-none focus:border-cyan-400/70" /></label>
        <label className="text-xs text-zinc-400">社交情报库<input value={socialPath} onChange={(event) => setSocialPath(event.target.value)} placeholder="D:\\knowledge\\social" className="mt-2 h-10 w-full rounded-md border border-white/10 bg-[#171717] px-3 text-sm text-zinc-100 outline-none focus:border-cyan-400/70" /></label>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button size="sm" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending || (!academicPath.trim() && !socialPath.trim())} className="bg-zinc-100 text-slate-950 hover:bg-white">{saveMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}保存路径</Button>
        {vaults?.map((vault) => <span key={vault.kind} className={`text-xs ${vault.available ? 'text-emerald-300' : 'text-amber-300'}`}>{vault.kind === 'academic' ? '学术库' : '社交库'}：{vault.available ? `${vault.note_count} 篇` : '未配置或不可访问'}</span>)}
      </div>
    </section>

    <div className="flex flex-wrap items-center gap-2">
      <button type="button" onClick={() => setKind('academic')} className={`rounded-md border px-3 py-1.5 text-xs ${kind === 'academic' ? 'border-cyan-400/70 bg-cyan-400/10 text-cyan-200' : 'border-white/10 bg-[#202020] text-zinc-400'}`}>学术库 {vaultByKind(vaults, 'academic')?.note_count ?? 0}</button>
      <button type="button" onClick={() => setKind('social')} className={`rounded-md border px-3 py-1.5 text-xs ${kind === 'social' ? 'border-cyan-400/70 bg-cyan-400/10 text-cyan-200' : 'border-white/10 bg-[#202020] text-zinc-400'}`}>社交库 {vaultByKind(vaults, 'social')?.note_count ?? 0}</button>
      <div className="relative ml-auto"><Search className="absolute left-2.5 top-2.5 w-4 h-4 text-zinc-500" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索标题或路径" className="h-9 w-56 rounded-md border border-white/10 bg-[#171717] pl-8 pr-3 text-sm text-zinc-100 outline-none focus:border-cyan-400/60" /></div>
    </div>

    {!activeVault?.available && <section className="rounded-xl border border-amber-400/20 bg-amber-400/5 p-5 text-sm text-amber-200">当前库未配置或目录不可访问。填写上方路径并保存后即可浏览。</section>}

    {activeVault?.available && <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <section className="rounded-xl border border-white/[0.08] bg-[#202020] p-3">
        <div className="mb-2 flex items-center justify-between px-1"><h3 className="text-sm font-medium">笔记</h3><span className="text-xs text-zinc-500">{notes.length} 篇</span></div>
        <div className="max-h-[560px] space-y-1 overflow-auto">
          {notesQuery.isLoading && <p className="py-6 text-center text-sm text-zinc-500">正在加载…</p>}
          {!notesQuery.isLoading && notes.length === 0 && <p className="py-6 text-center text-sm text-zinc-500">没有匹配的笔记。</p>}
          {notes.map((note) => <button key={note.path} type="button" onClick={() => setSelectedNote(note.path)} className={`w-full rounded-md border px-3 py-2 text-left ${selectedNote === note.path ? 'border-cyan-400/60 bg-cyan-400/10' : 'border-transparent hover:bg-white/[0.04]'}`}><p className="truncate text-sm text-zinc-200">{note.title || note.path}</p><p className="mt-0.5 truncate text-[10px] text-zinc-500">{note.path}</p></button>)}
        </div>
      </section>
      <section className="rounded-xl border border-white/[0.08] bg-[#202020] p-4">
        {!selectedNote && <div className="flex min-h-[240px] items-center justify-center text-sm text-zinc-500">从左侧选择一篇笔记查看内容。</div>}
        {selectedNote && noteQuery.isLoading && <p className="py-10 text-center text-sm text-zinc-500"><Loader2 className="mx-auto mb-2 w-4 h-4 animate-spin" />正在读取…</p>}
        {selectedNote && noteQuery.isError && <p className="py-10 text-center text-sm text-rose-300">读取失败：{noteQuery.error.message}</p>}
        {selectedNote && noteQuery.data && <div>
          <div className="flex items-start justify-between gap-3"><h3 className="text-sm font-medium text-zinc-100">{String(noteQuery.data.meta.title || selectedNote.split(/[\\/]/).pop())}</h3><span className="text-[11px] text-zinc-500">{String(noteQuery.data.meta.created || '')}</span></div>
          <p className="mt-1 text-[11px] text-zinc-500">{selectedNote}</p>
          <pre className="mt-3 max-h-[520px] overflow-auto whitespace-pre-wrap rounded-lg border border-white/[0.06] bg-[#171717] p-4 text-xs leading-6 text-zinc-300">{noteQuery.data.content}</pre>
        </div>}
      </section>
    </div>}
  </div>
}
