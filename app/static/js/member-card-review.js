// static/js/member-card-review.js
document.addEventListener('DOMContentLoaded', function() {
    // ========== CONFIGURAÇÕES ==========
    const WIDTH = 856, HEIGHT = 540;  // Tamanho base do cartão
    
    // ========== ELEMENTOS DOM ==========
    const image = document.getElementById('cropper-image');
    const frontPreview = document.getElementById('front-preview');
    const backPreview = document.getElementById('back-preview');
    const loadingOverlay = document.getElementById('loading');
    
    // ========== ESTADO ==========
    let cropper = null;
    let currentPhotoSource = 'profile';
    let originalPhotoUrl = image.src;
    
    // ========== INICIALIZAÇÃO ==========
    function initCropper() {
        if (cropper) cropper.destroy();
        
        cropper = new Cropper(image, {
            aspectRatio: 0.75,  // 3:4 para foto de identificação
            viewMode: 1,
            autoCropArea: 0.8,
            rotatable: true,
            zoomable: true,
            scalable: true,
            minCropBoxWidth: 100,
            minCropBoxHeight: 100,
            ready: function() {
                updatePreviews();
            },
            crop: function() {
                updatePreviews();
            },
            zoom: function() {
                updatePreviews();
            },
            rotate: function() {
                updatePreviews();
            }
        });
    }
    
    // ========== FUNÇÕES DE PREVIEW ==========
    function updatePreviews() {
        // Atualiza frente
        updateCardPreview('front', frontPreview, window.cardData.church.frontLayout, getFrontData());
        // Atualiza verso
        updateCardPreview('back', backPreview, window.cardData.church.backLayout, getBackData());
    }
    
    function updateCardPreview(side, container, layout, data) {
        const bgUrl = side === 'front' ? window.cardData.church.frontBg : window.cardData.church.backBg;
        
        // Cria HTML do preview
        let html = `<div class="preview-card" style="background-image: url('${bgUrl}'); background-size: cover;">`;
        
        // Adiciona campos de texto
        for (const [field, fieldData] of Object.entries(layout)) {
            if (!data[field]) continue;
            
            const x = fieldData.x || 0;
            const y = fieldData.y || 0;
            const width = fieldData.width || 200;
            
            html += `<div class="field-value ${field}" style="left: ${x}px; top: ${y}px; width: ${width}px;">`;
            
            if (field === 'disclaimer') {
                html += data[field];
            } else if (field === 'signature') {
                html += data[field].replace('\n', '<br>');
            } else {
                html += data[field];
            }
            
            html += '</div>';
        }
        
        // Adiciona foto (apenas frente)
        if (side === 'front' && layout.photo) {
            const photoData = layout.photo;
            const photoX = photoData.x || 40;
            const photoY = photoData.y || 140;
            const photoW = photoData.width || 220;
            const photoH = photoData.height || 280;
            
            // Obtém foto cropada
            if (cropper) {
                const canvas = cropper.getCroppedCanvas({
                    width: photoW,
                    height: photoH
                });
                html += `<img src="${canvas.toDataURL()}" style="position: absolute; left: ${photoX}px; top: ${photoY}px; width: ${photoW}px; height: ${photoH}px; object-fit: cover; border-radius: 4px;">`;
            } else if (originalPhotoUrl) {
                html += `<img src="${originalPhotoUrl}" style="position: absolute; left: ${photoX}px; top: ${photoY}px; width: ${photoW}px; height: ${photoH}px; object-fit: cover; border-radius: 4px;">`;
            }
        }
        
        html += '</div>';
        container.innerHTML = html;
    }
    
    function getFrontData() {
        return {
            name: window.cardData.member.name,
            role: window.cardData.member.role,
            marital_status: window.cardData.member.maritalStatus,
            birth_date: window.cardData.member.birthDate
        };
    }
    
    function getBackData() {
        return {
            filiacao: window.cardData.church.name,
            document: window.cardData.member.documents,
            conversion_date: window.cardData.member.conversionDate,
            baptism_date: window.cardData.member.baptismDate,
            disclaimer: window.cardData.disclaimer,
            signature: window.cardData.signature
        };
    }
    
    // ========== CONTROLES DA FOTO ==========
    
    // Opções de fonte da foto
    document.querySelectorAll('.photo-option').forEach(option => {
        option.addEventListener('click', function() {
            document.querySelectorAll('.photo-option').forEach(opt => opt.classList.remove('selected'));
            this.classList.add('selected');
            
            currentPhotoSource = this.dataset.source;
            
            if (currentPhotoSource === 'upload') {
                document.getElementById('upload-area').style.display = 'block';
                document.getElementById('cropper-container').style.display = 'block';
            } else if (currentPhotoSource === 'default') {
                document.getElementById('upload-area').style.display = 'none';
                document.getElementById('cropper-container').style.display = 'block';
                
                // Carrega foto padrão
                image.src = '/static/img/default-avatar.png';
                cropper.replace('/static/img/default-avatar.png');
            } else {
                document.getElementById('upload-area').style.display = 'none';
                document.getElementById('cropper-container').style.display = 'block';
                
                // Volta para foto original do perfil
                image.src = originalPhotoUrl;
                cropper.replace(originalPhotoUrl);
            }
        });
    });
    
    // Upload de nova foto
    document.getElementById('photo-upload').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        // Valida tamanho (5MB)
        if (file.size > 5 * 1024 * 1024) {
            alert('Arquivo muito grande! Máximo 5MB.');
            return;
        }
        
        // Valida tipo
        if (!file.type.startsWith('image/')) {
            alert('Por favor, selecione uma imagem válida.');
            return;
        }
        
        const reader = new FileReader();
        reader.onload = function(event) {
            image.src = event.target.result;
            if (cropper) {
                cropper.replace(event.target.result);
            } else {
                initCropper();
            }
        };
        reader.readAsDataURL(file);
    });
    
    // Controles de rotação
    document.getElementById('rotate-left').addEventListener('click', function() {
        if (cropper) cropper.rotate(-90);
    });
    
    document.getElementById('rotate-right').addEventListener('click', function() {
        if (cropper) cropper.rotate(90);
    });
    
    // Espelhamento
    document.getElementById('flip-x').addEventListener('click', function() {
        if (cropper) {
            const data = cropper.getData();
            cropper.scale(-data.scaleX || -1, data.scaleY || 1);
        }
    });
    
    document.getElementById('flip-y').addEventListener('click', function() {
        if (cropper) {
            const data = cropper.getData();
            cropper.scale(data.scaleX || 1, -data.scaleY || -1);
        }
    });
    
    // Zoom slider
    document.getElementById('zoom-slider').addEventListener('input', function(e) {
        if (cropper) {
            cropper.zoomTo(parseFloat(e.target.value));
        }
    });
    
    // Reset
    document.getElementById('reset-crop').addEventListener('click', function() {
        if (cropper) cropper.reset();
    });
    
    // ========== GERAÇÃO DO CARTÃO ==========
    
    document.getElementById('generate-card').addEventListener('click', async function() {
        loadingOverlay.classList.add('active');
        
        try {
            const canvas = cropper.getCroppedCanvas({
                width: 400,
                height: 533,  // Mantém proporção 3:4
                imageSmoothingEnabled: true,
                imageSmoothingQuality: 'high'
            });
            
            const croppedPhoto = canvas.toDataURL('image/png', 0.95);
            
            const form = new FormData();
            form.append('cropped_photo', croppedPhoto);
            form.append('photo_source', currentPhotoSource);
            
            const response = await fetch('{{ url_for('admin.member_card', id=member.id) }}', {
                method: 'POST',
                body: form
            });
            
            if (!response.ok) throw new Error('Erro na geração');
            
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `cartao_membro_{{ member.name.replace(" ", "_") }}.png`;
            a.click();
            URL.revokeObjectURL(url);
            
        } catch (err) {
            alert('Erro ao gerar o cartão: ' + err.message);
        } finally {
            loadingOverlay.classList.remove('active');
        }
    });
    
    // Download preview
    document.getElementById('download-preview').addEventListener('click', function() {
        // Captura os previews como imagem
        html2canvas(frontPreview).then(canvas => {
            const url = canvas.toDataURL('image/png');
            const a = document.createElement('a');
            a.href = url;
            a.download = `preview_frente_{{ member.name.replace(" ", "_") }}.png`;
            a.click();
        });
    });
    
    // ========== INICIALIZA ==========
    initCropper();
    updatePreviews();
});