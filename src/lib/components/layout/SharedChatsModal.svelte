<script lang="ts">
	import type { Writable } from 'svelte/store';
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { deleteSharedChatById, getSharedChatList } from '$lib/apis/chats';
	import Modal from '$lib/components/common/Modal.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import SharedChatsTable from './SharedChatsTable.svelte';

	const i18n: Writable<any> = getContext('i18n');
	const PAGE_SIZE = 20;

	export let show = false;
	export let onUpdate = () => {};

	let query = '';
	let orderBy = 'updated_at';
	let direction = 'desc';
	let page = 1;
	let chatList: any[] = [];
	let loading = false;
	let hasNextPage = false;
	let selectedChatIds = new Set<string>();
	let searchDebounceTimeout: ReturnType<typeof setTimeout> | null = null;
	let requestVersion = 0;

	$: hasPrevPage = page > 1;
	$: selectedCount = selectedChatIds.size;
	$: totalOnPage = chatList.length;

	const loadChats = async () => {
		if (!show) return;
		const currentRequest = ++requestVersion;
		loading = true;

		const filter = {
			...(query ? { query } : {}),
			order_by: orderBy,
			direction
		};

		const res = await getSharedChatList(localStorage.token, page, filter).catch((error) => {
			toast.error(`${error}`);
			return [];
		});

		if (currentRequest !== requestVersion) return;
		chatList = res ?? [];
		hasNextPage = (res?.length ?? 0) >= PAGE_SIZE;
		loading = false;
	};

	const scheduleLoad = () => {
		if (searchDebounceTimeout) {
			clearTimeout(searchDebounceTimeout);
		}
		searchDebounceTimeout = setTimeout(loadChats, 300);
	};

	const setSortKey = (key: string) => {
		if (orderBy === key) {
			direction = direction === 'asc' ? 'desc' : 'asc';
		} else {
			orderBy = key;
			direction = 'asc';
		}
		page = 1;
		loadChats();
	};

	const toggleSelectChat = (chatId: string, checked: boolean) => {
		const next = new Set(selectedChatIds);
		if (checked) {
			next.add(chatId);
		} else {
			next.delete(chatId);
		}
		selectedChatIds = next;
	};

	const toggleSelectAllPage = (checked: boolean) => {
		const next = new Set(selectedChatIds);
		for (const chat of chatList) {
			if (checked) {
				next.add(chat.id);
			} else {
				next.delete(chat.id);
			}
		}
		selectedChatIds = next;
	};

	const unshareSingle = async (chatId: string) => {
		const res = await deleteSharedChatById(localStorage.token, chatId).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res === true) {
			const next = new Set(selectedChatIds);
			next.delete(chatId);
			selectedChatIds = next;
			toast.success($i18n.t('Chat unshared successfully.'));
			onUpdate();
			loadChats();
		} else if (res === false) {
			toast.error($i18n.t('Failed to unshare chat.'));
		}
	};

	const unshareSelected = async () => {
		if (selectedChatIds.size === 0) return;
		const selectedIds = [...selectedChatIds];
		const results = await Promise.all(
			selectedIds.map((id) => deleteSharedChatById(localStorage.token, id).catch(() => false))
		);
		const successCount = results.filter((r) => r === true).length;
		const failedCount = selectedIds.length - successCount;

		if (successCount > 0) {
			toast.success($i18n.t('{{count}} chats unshared successfully.', { count: successCount }));
		}
		if (failedCount > 0) {
			toast.error($i18n.t('{{count}} chats failed to unshare.', { count: failedCount }));
		}

		selectedChatIds = new Set();
		onUpdate();
		loadChats();
	};

	const prevPage = () => {
		if (!hasPrevPage) return;
		page -= 1;
		loadChats();
	};

	const nextPage = () => {
		if (!hasNextPage) return;
		page += 1;
		loadChats();
	};

	$: if (show) {
		query;
		orderBy;
		direction;
		page;
		scheduleLoad();
	} else {
		if (searchDebounceTimeout) {
			clearTimeout(searchDebounceTimeout);
			searchDebounceTimeout = null;
		}
		page = 1;
		query = '';
		selectedChatIds = new Set();
	}
</script>

<Modal size="xl" bind:show>
	<div class="px-5 pt-4 pb-4 dark:text-gray-200">
		<div class="flex items-center justify-between mb-3">
			<div class="text-lg font-medium">{$i18n.t('Shared Chats')}</div>
			<button
				class="p-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-850"
				on:click={() => {
					show = false;
				}}
			>
				<XMark className="size-4" strokeWidth="2.5" />
			</button>
		</div>

		<div class="flex items-center justify-between gap-3 mb-3">
			<div class="text-xs text-gray-500 dark:text-gray-400">
				{$i18n.t('Total')}: {totalOnPage} | {$i18n.t('Selected')}: {selectedCount}
			</div>
			<div class="flex items-center gap-2">
				<input
					class="w-64 text-sm px-3 py-1.5 rounded-lg outline-hidden bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-850"
					bind:value={query}
					placeholder={$i18n.t('Search Chats')}
					maxlength="500"
					on:input={() => {
						page = 1;
					}}
				/>
				<button
					class="px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-800 disabled:opacity-50"
					disabled={selectedCount === 0 || loading}
					on:click={unshareSelected}
				>
					{$i18n.t('Unshare Selected')}
				</button>
				<button
					class="px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-800 disabled:opacity-50"
					disabled={selectedCount === 0 || loading}
					on:click={() => {
						selectedChatIds = new Set();
					}}
				>
					{$i18n.t('Clear Selection')}
				</button>
			</div>
		</div>

		<SharedChatsTable
			{chatList}
			{query}
			{loading}
			{page}
			{hasPrevPage}
			{hasNextPage}
			{orderBy}
			{direction}
			{selectedChatIds}
			onToggleSort={setSortKey}
			onToggleSelectAllPage={toggleSelectAllPage}
			onToggleSelectChat={toggleSelectChat}
			onPrevPage={prevPage}
			onNextPage={nextPage}
			onUnshareSingle={unshareSingle}
		/>
	</div>
</Modal>
