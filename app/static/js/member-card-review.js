// static/js/member-card-review.js
// CSS FORÇADO - Garante que o cartão apareça
(function() {
    const style = document.createElement('style');
    style.textContent = `
        #card-preview-front, #card-preview-back {
            position: relative !important;
            z-index: 9999 !important;
            opacity: 1 !important;
            visibility: visible !important;
            display: block !important;
            background-color: #f0f0f0 !important;
            border: 5px solid red !important;
            min-height: 540px !important;
            overflow: visible !important;
        }
        
        #card-preview-front * , #card-preview-back * {
            position: absolute;
            z-index: 10000 !important;
            background-color: rgba(255,255,255,0.9) !important;
            border: 2px solid blue !important;
            color: black !important;
            font-size: 16px !important;
            padding: 5px !important;
        }
        
        .member-photo-container-preview {
            z-index: 10001 !important;
            background-color: #e9ecef !important;
            border: 3px solid green !important;
        }
        
        .field-value {
            background-color: rgba(255,255,255,0.95) !important;
            border: 2px dashed #0d6efd !important;
        }
    `;
    document.head.appendChild(style);
    console.log('✅ CSS de emergência aplicado');
})();
// Arquivo COMPLETO com todas as funcionalidades

(function() {
    console.log('🚀 Iniciando member-card-review.js - Versão Completa');
    
    // ========== CONFIGURAÇÕES ==========
    const CARD_WIDTH = 856;
    const CARD_HEIGHT = 540;

    // ========== ESTADO GLOBAL ==========
    let currentPhotoUrl = '';
    let currentZoom = 1.0;
    let currentPhotoOffset = { x: 0, y: 0 };
    let isDraggingPhoto = false;
    let dragStartX, dragStartY;
    let customPhotoPath = null;

    // ========== ELEMENTOS DOM ==========
    let cardPreviewFront, cardPreviewBack, photoUploadInput, zoomSlider, zoomValueSpan, btnReset, btnEmit, loadingIndicator;

    // ========== FUNÇÃO PARA AGUARDAR ELEMENTOS ==========
    function waitForElement(selector, callback, maxAttempts = 50) {
        let attempts = 0;
        const interval = setInterval(() => {
            const element = document.querySelector(selector);
            attempts++;
            
            if (element) {
                console.log(`✅ Elemento ${selector} encontrado após ${attempts} tentativas`);
                clearInterval(interval);
                callback(element);
            } else if (attempts >= maxAttempts) {
                console.error(`❌ Elemento ${selector} não encontrado após ${maxAttempts} tentativas`);
                clearInterval(interval);
            }
        }, 100);
    }

    // ========== FUNÇÕES DE DRAG DA FOTO ==========
    function startPhotoDrag(e) {
        e.preventDefault();
        const photoContainer = document.getElementById('member-photo-container-preview');
        if (!photoContainer) return;
        
        isDraggingPhoto = true;
        dragStartX = e.clientX - currentPhotoOffset.x;
        dragStartY = e.clientY - currentPhotoOffset.y;
        
        document.addEventListener('mousemove', dragPhoto);
        document.addEventListener('mouseup', stopPhotoDrag);
        
        photoContainer.style.cursor = 'grabbing';
    }

    function dragPhoto(e) {
        if (!isDraggingPhoto) return;
        
        currentPhotoOffset.x = e.clientX - dragStartX;
        currentPhotoOffset.y = e.clientY - dragStartY;
        updatePhotoTransform();
    }

    function stopPhotoDrag() {
        isDraggingPhoto = false;
        document.removeEventListener('mousemove', dragPhoto);
        document.removeEventListener('mouseup', stopPhotoDrag);
        
        const photoContainer = document.getElementById('member-photo-container-preview');
        if (photoContainer) {
            photoContainer.style.cursor = 'move';
        }
    }

    function updatePhotoTransform() {
        const imgElement = document.getElementById('preview-photo-img');
        if (imgElement) {
            imgElement.style.transform = `scale(${currentZoom}) translate(${currentPhotoOffset.x}px, ${currentPhotoOffset.y}px)`;
        }
    }

    // ========== FUNÇÃO PRINCIPAL DE RENDERIZAÇÃO ==========
    function renderCard(side, container) {
        if (!container) {
            console.error(`❌ Container ${side} não disponível`);
            return;
        }
        
        console.log(`🎨 Renderizando ${side}...`);
        container.innerHTML = '';
        
        // Configurações básicas do container
        container.style.position = 'relative';
        container.style.width = CARD_WIDTH + 'px';
        container.style.height = CARD_HEIGHT + 'px';
        container.style.overflow = 'hidden';
        container.style.borderRadius = '8px';
        container.style.boxShadow = '0 4px 20px rgba(0,0,0,0.15)';
        container.style.border = '1px solid #dee2e6'; // Borda sutil
        
        const data = window.cardData;
        if (!data) {
            console.error('❌ cardData não encontrado');
            container.innerHTML = '<div style="padding:20px; color:red;">Erro: Dados do cartão não carregados</div>';
            return;
        }
        
        const isFront = (side === 'front');
        
        // 1. APLICAR BACKGROUND
        const bgUrl = isFront ? data.church?.frontBg : data.church?.backBg;
        if (bgUrl && bgUrl.trim() !== '') {
            console.log(`🖼️ Background ${side}:`, bgUrl);
            container.style.backgroundImage = `url('${bgUrl}')`;
            container.style.backgroundSize = 'cover';
            container.style.backgroundPosition = 'center';
            container.style.backgroundRepeat = 'no-repeat';
        } else {
            console.warn(`⚠️ Sem background para ${side}`);
            container.style.backgroundColor = '#f8f9fa';
        }
        
        // 2. RENDERIZAR LAYOUT
        const layout = isFront ? data.church?.frontLayout : data.church?.backLayout;
        if (!layout || Object.keys(layout).length === 0) {
            console.warn(`⚠️ Layout vazio para ${side}`);
            const msg = document.createElement('div');
            msg.textContent = `Layout ${side} não configurado`;
            msg.style.position = 'absolute';
            msg.style.top = '50%';
            msg.style.left = '50%';
            msg.style.transform = 'translate(-50%, -50%)';
            msg.style.backgroundColor = 'rgba(255,193,7,0.8)';
            msg.style.padding = '10px';
            msg.style.borderRadius = '4px';
            container.appendChild(msg);
        } else {
            // Renderizar campos de texto
            Object.entries(layout).forEach(([fieldName, fieldLayout]) => {
                if (fieldName === 'photo') return; // Foto será tratada separadamente
                
                // Determinar valor do campo
                let fieldValue = '';
                switch(fieldName) {
                    case 'name':
                        fieldValue = data.member?.name || '';
                        break;
                    case 'role':
                        fieldValue = data.member?.role || '';
                        break;
                    case 'marital_status':
                        fieldValue = data.member?.maritalStatus || '';
                        break;
                    case 'birth_date':
                        fieldValue = data.member?.birthDate || '';
                        break;
                    case 'filiacao':
                        fieldValue = data.member?.filiation || data.church?.name || '';
                        break;
                    case 'document':
                        fieldValue = data.member?.documents || '';
                        break;
                    case 'conversion_date':
                        fieldValue = data.member?.conversionDate || '';
                        break;
                    case 'baptism_date':
                        fieldValue = data.member?.baptismDate || '';
                        break;
                    case 'disclaimer':
                        fieldValue = data.disclaimer || '';
                        break;
                    case 'signature':
                        fieldValue = data.signature ? data.signature.replace(/\\n/g, '<br>') : '';
                        break;
                    default:
                        fieldValue = '';
                }
                
                if (fieldValue && fieldValue.trim() !== '') {
                    try {
                        const fieldEl = document.createElement('div');
                        fieldEl.className = `field-value field-${fieldName}`;
                        fieldEl.innerHTML = fieldValue;
                        
                        // Posicionamento
                        fieldEl.style.position = 'absolute';
                        fieldEl.style.left = (fieldLayout.x || 0) + 'px';
                        fieldEl.style.top = (fieldLayout.y || 0) + 'px';
                        fieldEl.style.width = (fieldLayout.width || 200) + 'px';
                        
                        if (fieldLayout.height) {
                            fieldEl.style.height = fieldLayout.height + 'px';
                        }
                        
                        // Estilo
                        fieldEl.style.backgroundColor = 'rgba(255, 255, 255, 0.7)';
                        fieldEl.style.padding = '5px';
                        fieldEl.style.fontSize = fieldLayout.font_size ? fieldLayout.font_size + 'px' : '14px';
                        fieldEl.style.color = fieldLayout.color || '#000000';
                        fieldEl.style.textAlign = fieldLayout.text_align || 'left';
                        fieldEl.style.fontWeight = fieldLayout.font_weight || 'normal';
                        fieldEl.style.overflow = 'hidden';
                        fieldEl.style.boxSizing = 'border-box';
                        fieldEl.style.zIndex = '2';
                        fieldEl.style.border = '1px dashed #0d6efd'; // Para debug
                        
                        container.appendChild(fieldEl);
                        console.log(`✅ Campo ${fieldName} renderizado`);
                    } catch (e) {
                        console.error(`Erro ao renderizar campo ${fieldName}:`, e);
                    }
                }
            });
        }
        
        // 3. RENDERIZAR FOTO (apenas frente)
        if (isFront) {
            const photoLayout = layout?.photo;
            const photoUrl = currentPhotoUrl || data.member?.profilePhotoUrl;
            
            if (photoLayout && photoUrl) {
                try {
                    console.log('📸 Renderizando foto');
                    
                    const photoContainer = document.createElement('div');
                    photoContainer.id = 'member-photo-container-preview';
                    photoContainer.className = 'member-photo-container-preview';
                    
                    // Posicionamento
                    photoContainer.style.position = 'absolute';
                    photoContainer.style.left = (photoLayout.x || 40) + 'px';
                    photoContainer.style.top = (photoLayout.y || 140) + 'px';
                    photoContainer.style.width = (photoLayout.width || 220) + 'px';
                    photoContainer.style.height = (photoLayout.height || 280) + 'px';
                    photoContainer.style.overflow = 'hidden';
                    photoContainer.style.cursor = 'move';
                    photoContainer.style.backgroundColor = '#e9ecef';
                    photoContainer.style.border = '2px solid #28a745'; // Borda verde para debug
                    photoContainer.style.zIndex = '3';
                    photoContainer.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
                    
                    const img = document.createElement('img');
                    img.id = 'preview-photo-img';
                    img.src = photoUrl;
                    img.alt = 'Foto do membro';
                    img.style.width = '100%';
                    img.style.height = '100%';
                    img.style.objectFit = 'cover';
                    img.style.transform = `scale(${currentZoom}) translate(${currentPhotoOffset.x}px, ${currentPhotoOffset.y}px)`;
                    img.style.transformOrigin = 'center';
                    img.style.transition = 'transform 0.1s ease';
                    img.style.pointerEvents = 'none';
                    
                    photoContainer.appendChild(img);
                    container.appendChild(photoContainer);
                    
                    // Adicionar evento de drag
                    photoContainer.addEventListener('mousedown', startPhotoDrag);
                    
                    console.log('✅ Foto renderizada');
                } catch (e) {
                    console.error('Erro ao renderizar foto:', e);
                }
            } else if (isFront) {
                // Placeholder para foto
                const placeholder = document.createElement('div');
                placeholder.style.position = 'absolute';
                placeholder.style.left = '40px';
                placeholder.style.top = '140px';
                placeholder.style.width = '220px';
                placeholder.style.height = '280px';
                placeholder.style.backgroundColor = '#e9ecef';
                placeholder.style.border = '2px dashed #6c757d';
                placeholder.style.display = 'flex';
                placeholder.style.alignItems = 'center';
                placeholder.style.justifyContent = 'center';
                placeholder.style.color = '#6c757d';
                placeholder.style.fontSize = '12px';
                placeholder.innerHTML = 'Sem foto';
                placeholder.style.zIndex = '1';
                container.appendChild(placeholder);
            }
        }
        
        console.log(`✅ Renderização do ${side} concluída`);
    }

    // ========== INICIALIZAR EVENT LISTENERS ==========
    function initializeEventListeners() {
        console.log('🎮 Inicializando event listeners...');
        
        // Upload de foto
        if (photoUploadInput) {
            photoUploadInput.addEventListener('change', function(e) {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        currentPhotoUrl = event.target.result;
                        customPhotoPath = 'data-url';
                        renderCard('front', cardPreviewFront);
                        renderCard('back', cardPreviewBack);
                    };
                    reader.readAsDataURL(file);
                }
            });
            console.log('✅ Event listener de upload adicionado');
        }

        // Zoom slider
        if (zoomSlider && zoomValueSpan) {
            zoomSlider.addEventListener('input', function(e) {
                currentZoom = parseFloat(e.target.value);
                zoomValueSpan.textContent = `${Math.round(currentZoom * 100)}%`;
                updatePhotoTransform();
            });
            console.log('✅ Event listener de zoom adicionado');
        }

        // Botão Reset
        if (btnReset) {
            btnReset.addEventListener('click', function() {
                currentZoom = 1.0;
                currentPhotoOffset = { x: 0, y: 0 };
                if (zoomSlider) zoomSlider.value = 1.0;
                if (zoomValueSpan) zoomValueSpan.textContent = '100%';
                currentPhotoUrl = window.cardData?.member?.profilePhotoUrl || '';
                customPhotoPath = null;
                if (photoUploadInput) photoUploadInput.value = '';
                
                renderCard('front', cardPreviewFront);
                renderCard('back', cardPreviewBack);
            });
            console.log('✅ Event listener de reset adicionado');
        }

        // Botão Emitir
        if (btnEmit) {
            btnEmit.addEventListener('click', async function() {
                if (loadingIndicator) loadingIndicator.style.display = 'block';
                btnEmit.disabled = true;

                try {
                    const response = await fetch(`/admin/member/card-generate/${window.cardData.member.id}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            photo_zoom: currentZoom,
                            photo_offset_x: currentPhotoOffset.x,
                            photo_offset_y: currentPhotoOffset.y,
                            custom_photo_path: customPhotoPath
                        })
                    });

                    if (!response.ok) {
                        throw new Error(`Erro HTTP: ${response.status}`);
                    }

                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `cartao_membro_${window.cardData.member.name.replace(/ /g, '_')}.png`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);

                } catch (error) {
                    console.error('Erro ao emitir cartão:', error);
                    alert('Erro ao emitir cartão: ' + error.message);
                } finally {
                    if (loadingIndicator) loadingIndicator.style.display = 'none';
                    btnEmit.disabled = false;
                }
            });
            console.log('✅ Event listener de emissão adicionado');
        }
    }

    // ========== FUNÇÃO PRINCIPAL DE INICIALIZAÇÃO ==========
    function initialize() {
        console.log('🔄 Inicializando sistema completo...');
        
        // Buscar elementos DOM
        cardPreviewFront = document.getElementById('card-preview-front');
        cardPreviewBack = document.getElementById('card-preview-back');
        photoUploadInput = document.getElementById('photo-upload');
        zoomSlider = document.getElementById('zoom-slider');
        zoomValueSpan = document.getElementById('zoom-value');
        btnReset = document.getElementById('btn-reset');
        btnEmit = document.getElementById('btn-emit');
        loadingIndicator = document.getElementById('loading-indicator');
        
        // Verificar cardData
        if (!window.cardData) {
            console.error('❌ cardData não encontrado!');
            return;
        }
        
        // Inicializar foto atual
        currentPhotoUrl = window.cardData.member?.profilePhotoUrl || '';
        
        console.log('📦 Dados carregados:', {
            member: window.cardData.member?.name,
            church: window.cardData.church?.name,
            hasFrontLayout: !!window.cardData.church?.frontLayout,
            hasBackLayout: !!window.cardData.church?.backLayout
        });
        
        // Tentativa 1: Renderizar imediatamente se os containers existirem
        if (cardPreviewFront && cardPreviewBack) {
            console.log('✅ Containers encontrados imediatamente');
            renderCard('front', cardPreviewFront);
            renderCard('back', cardPreviewBack);
            initializeEventListeners();
            return;
        }
        
        // Tentativa 2: Aguardar DOM pronto
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                console.log('📦 DOMContentLoaded disparado');
                cardPreviewFront = document.getElementById('card-preview-front');
                cardPreviewBack = document.getElementById('card-preview-back');
                
                if (cardPreviewFront && cardPreviewBack) {
                    renderCard('front', cardPreviewFront);
                    renderCard('back', cardPreviewBack);
                    initializeEventListeners();
                }
            });
        }
        
        // Tentativa 3: Aguardar elementos especificamente
        waitForElement('#card-preview-front', (front) => {
            cardPreviewFront = front;
            cardPreviewBack = document.getElementById('card-preview-back');
            
            if (cardPreviewFront && cardPreviewBack) {
                renderCard('front', cardPreviewFront);
                renderCard('back', cardPreviewBack);
                initializeEventListeners();
            }
        });
        
        // Tentativa 4: Última tentativa após 2 segundos
        setTimeout(() => {
            console.log('⏰ Tentativa atrasada...');
            cardPreviewFront = document.getElementById('card-preview-front');
            cardPreviewBack = document.getElementById('card-preview-back');
            
            if (cardPreviewFront && cardPreviewBack) {
                if (cardPreviewFront.children.length === 0) { // Só renderiza se estiver vazio
                    renderCard('front', cardPreviewFront);
                    renderCard('back', cardPreviewBack);
                    initializeEventListeners();
                }
            }
        }, 2000);
    }

    // Iniciar tudo
    initialize();
})();