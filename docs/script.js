document.addEventListener('DOMContentLoaded', function() {
    let calendar;
    let allEvents = [];
    let companyFilter = '';
    let typeFilter = '';

    // 加载数据
    fetch('../data/calendar_data.json')
        .then(response => response.json())
        .then(data => {
            allEvents = data.map(item => ({
                id: item.id,
                title: `${item.company} - ${item.title}`,
                start: item.publish_date,
                extendedProps: {
                    company: item.company,
                    type: item.type,
                    open_source: item.open_source,
                    summary: item.summary,
                    details: item.details,
                    url: item.url,
                    tags: item.tags
                }
            }));
            // 填充筛选下拉框
            populateFilters(allEvents);
            renderCalendar();
        })
        .catch(error => console.error('加载数据失败:', error));

    function populateFilters(events) {
        const companies = [...new Set(events.map(e => e.extendedProps.company))].sort();
        const types = [...new Set(events.map(e => e.extendedProps.type))].sort();
        const companySelect = document.getElementById('companyFilter');
        const typeSelect = document.getElementById('typeFilter');
        companies.forEach(c => {
            const option = document.createElement('option');
            option.value = c;
            option.textContent = c;
            companySelect.appendChild(option);
        });
        types.forEach(t => {
            const option = document.createElement('option');
            option.value = t;
            option.textContent = t;
            typeSelect.appendChild(option);
        });
    }

    function renderCalendar() {
        const filteredEvents = allEvents.filter(event => {
            return (companyFilter === '' || event.extendedProps.company === companyFilter) &&
                   (typeFilter === '' || event.extendedProps.type === typeFilter);
        });
        const calendarEl = document.getElementById('calendar');
        if (calendar) {
            calendar.destroy();
        }
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            locale: 'zh-cn',
            events: filteredEvents,
            eventClick: function(info) {
                showModal(info.event.extendedProps);
            },
            dateClick: function(info) {
                // 可选：点击日期显示当天所有事件
                const dateStr = info.dateStr;
                const dayEvents = filteredEvents.filter(e => e.start === dateStr);
                if (dayEvents.length > 0) {
                    let content = `<h3>${dateStr} 发布</h3><ul>`;
                    dayEvents.forEach(e => {
                        content += `<li><strong>${e.title}</strong> - ${e.extendedProps.summary}</li>`;
                    });
                    content += '</ul>';
                    showModalContent(content);
                }
            }
        });
        calendar.render();
    }

    function showModal(props) {
        const content = `
            <h3>${props.company} - ${props.title}</h3>
            <p><strong>日期：</strong>${props.start}</p>
            <p><strong>类型：</strong>${props.type}</p>
            <p><strong>开源：</strong>${props.open_source}</p>
            <p><strong>简介：</strong>${props.summary || '暂无'}</p>
            <p><strong>详情：</strong>${props.details || '暂无'}</p>
            <p><strong>标签：</strong>${props.tags || '无'}</p>
            <p><a href="${props.url}" target="_blank">查看原文</a></p>
        `;
        showModalContent(content);
    }

    function showModalContent(html) {
        const modal = document.getElementById('modal');
        const modalBody = document.getElementById('modal-body');
        modalBody.innerHTML = html;
        modal.style.display = 'block';
    }

    // 关闭模态框
    const closeBtn = document.querySelector('.close');
    closeBtn.onclick = function() {
        document.getElementById('modal').style.display = 'none';
    };
    window.onclick = function(event) {
        if (event.target == document.getElementById('modal')) {
            document.getElementById('modal').style.display = 'none';
        }
    };

    // 筛选事件监听
    document.getElementById('companyFilter').addEventListener('change', function(e) {
        companyFilter = e.target.value;
        renderCalendar();
    });
    document.getElementById('typeFilter').addEventListener('change', function(e) {
        typeFilter = e.target.value;
        renderCalendar();
    });
    document.getElementById('resetBtn').addEventListener('click', function() {
        companyFilter = '';
        typeFilter = '';
        document.getElementById('companyFilter').value = '';
        document.getElementById('typeFilter').value = '';
        renderCalendar();
    });
});